"""
core/openclaw_engine.py
─────────────────────────────────────────────────────────────────────────────
Moteur d'orchestration OpenClaw.
Reçoit une commande brute (texte ou JSON), l'analyse, la valide, puis la
route vers l'agent compétent (facturation, planning, etc.).
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from json_repair import repair_json
from loguru import logger
from pydantic import ValidationError

from brain.prompts import EXTRACTION_SYSTEM_PROMPT, BILAN_JOURNEE_PROMPT
from storage.local_db import LocalDB
from agents.chrono_agent import ChronoAgent


# ─── Schéma de commande validé par Pydantic ──────────────────────────────────
from pydantic import BaseModel, Field


ACTIONS_FACTURATION = {"ajouter_devis", "creer_facture", "modifier_devis", "supprimer_ligne", "ajouter_commande"}
ACTIONS_CHRONO = {"debut_chantier", "fin_chantier"}
ACTIONS_BILAN = {"bilan_journee"}


class CommandeValidee(BaseModel):
    client: str = Field(default="", description="Nom du client")
    item: str = Field(default="", description="Article ou prestation")
    quantite: float = Field(default=1.0, gt=0, description="Quantité (doit être > 0)")
    action: str = Field(
        ...,
        pattern="^(ajouter_devis|creer_facture|modifier_devis|supprimer_ligne|ajouter_commande|debut_chantier|fin_chantier|bilan_journee)$",
        description="Action à réaliser",
    )
    notes: str = Field(default="", description="Notes libres optionnelles")


# ─── Moteur principal ─────────────────────────────────────────────────────────
class OpenClawEngine:
    """
    Orchestre le pipeline complet :
    texte brut  →  JSON via Ollama  →  validation Pydantic  →  agent métier
    """

    def __init__(self, ollama_url: str, model: str, db: LocalDB):
        self.ollama_url = ollama_url
        self.model = model
        self.db = db
        self.chrono = ChronoAgent(db=db)

    # ── Étape 1 : Extraction via LLM local ───────────────────────────────────
    def extraire_json(self, texte: str) -> dict[str, Any]:
        """Envoie le texte à Ollama et récupère un JSON structuré."""
        logger.info(f"[OpenClaw] Extraction depuis : '{texte}'")

        payload = {
            "model": self.model,
            "prompt": f"{EXTRACTION_SYSTEM_PROMPT}\n\nTexte à analyser : {texte}",
            "stream": False,
        }

        try:
            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            logger.debug(f"[OpenClaw] Réponse LLM brute : {raw}")

            # json_repair nettoie les JSON malformés que le LLM peut produire
            repaired = repair_json(raw)
            return json.loads(repaired)

        except httpx.HTTPError as e:
            logger.error(f"[OpenClaw] Erreur HTTP Ollama : {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[OpenClaw] JSON illisible même après réparation : {e}")
            raise

    # ── Étape 2 : Validation des données ─────────────────────────────────────
    def valider(self, data: dict[str, Any]) -> CommandeValidee:
        """Valide le JSON extrait via Pydantic. Lève ValidationError si invalide."""
        try:
            commande = CommandeValidee(**data)
            logger.success(f"[OpenClaw] Commande validée : {commande}")
            return commande
        except ValidationError as e:
            logger.warning(f"[OpenClaw] Validation échouée : {e}")
            raise

    # ── Étape 3 : Sauvegarde locale (offline-first) ───────────────────────────
    def sauvegarder_offline(self, commande: CommandeValidee) -> int:
        """Persiste la commande en local avant tout envoi réseau."""
        cmd_id = self.db.inserer_commande(commande.model_dump())
        logger.info(f"[OpenClaw] Commande #{cmd_id} sauvegardée offline")
        return cmd_id

    # ── Bilan journée via Ollama local ────────────────────────────────────────
    def _generer_bilan(self) -> str:
        """Lit les activités du jour et génère un résumé via Ollama."""
        import json as _json
        activites = self.db.lire_activites_aujourd_hui()
        payload = {
            "model": self.model,
            "prompt": f"{BILAN_JOURNEE_PROMPT}\n\nActivités du jour :\n{_json.dumps(activites, ensure_ascii=False, indent=2)}",
            "stream": False,
        }
        try:
            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json().get("response", "Aucune activité enregistrée aujourd'hui.")
        except Exception as e:
            logger.error(f"[OpenClaw] Erreur bilan Ollama : {e}")
            # Bilan textuel minimal sans LLM
            cmds = len(activites.get("commandes", []))
            chronos = activites.get("chronos", [])
            total_h = sum(c.get("duree_h") or 0 for c in chronos)
            return f"Aujourd'hui : {cmds} commande(s), {total_h:.1f}h de chantier."

    # ── Pipeline complet ──────────────────────────────────────────────────────
    def traiter(self, texte: str) -> dict:
        """
        Pipeline principal :
        texte → extraction → validation → routing selon action

        Retourne un dict avec les clés :
          - type : "facturation" | "chrono" | "bilan"
          - message : confirmation textuelle
          - cmd_id : ID local (pour les actions de facturation uniquement)
          - commande : CommandeValidee (pour les actions de facturation uniquement)
        """
        data = self.extraire_json(texte)
        commande = self.valider(data)
        action = commande.action

        # ── Chrono ────────────────────────────────────────────────────────────
        if action == "debut_chantier":
            msg = self.chrono.demarrer(commande.client)
            return {"type": "chrono", "message": msg}

        if action == "fin_chantier":
            chrono_data, payload_factu = self.chrono.arreter()
            if payload_factu is None:
                return {"type": "chrono", "message": "Aucun chrono actif à arrêter."}
            # Sauvegarder la commande de facturation pour sync
            from pydantic import ValidationError
            try:
                cmd_factu = CommandeValidee(**payload_factu)
                cmd_id = self.sauvegarder_offline(cmd_factu)
                duree = chrono_data["duree_h"]
                msg = f"Chantier terminé — {duree:.2f}h pour {chrono_data['client']}. Facturation en cours."
                return {"type": "chrono", "message": msg, "cmd_id": cmd_id, "commande": cmd_factu}
            except ValidationError as e:
                logger.error(f"[OpenClaw] Payload chrono invalide : {e}")
                return {"type": "chrono", "message": "Erreur lors de la création de la facture."}

        # ── Bilan journée ─────────────────────────────────────────────────────
        if action == "bilan_journee":
            bilan = self._generer_bilan()
            logger.info(f"[OpenClaw] Bilan journée : {bilan}")
            return {"type": "bilan", "message": bilan}

        # ── Facturation (comportement original) ───────────────────────────────
        cmd_id = self.sauvegarder_offline(commande)
        return {"type": "facturation", "cmd_id": cmd_id, "commande": commande, "message": f"Commande #{cmd_id} sauvegardée."}
