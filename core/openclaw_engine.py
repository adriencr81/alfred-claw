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

from brain.prompts import EXTRACTION_SYSTEM_PROMPT
from storage.local_db import LocalDB


# ─── Schéma de commande validé par Pydantic ──────────────────────────────────
from pydantic import BaseModel, Field


class CommandeValidee(BaseModel):
    client: str = Field(..., min_length=1, description="Nom du client")
    item: str = Field(..., min_length=1, description="Article ou prestation")
    quantite: float = Field(..., gt=0, description="Quantité (doit être > 0)")
    action: str = Field(
        ...,
        pattern="^(ajouter_devis|creer_facture|modifier_devis|supprimer_ligne|ajouter_commande)$",
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
                timeout=30.0,
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

    # ── Pipeline complet ──────────────────────────────────────────────────────
    def traiter(self, texte: str) -> tuple[int, CommandeValidee]:
        """
        Pipeline principal :
        texte → extraction → validation → sauvegarde locale
        Retourne (id_local, CommandeValidee)
        """
        data = self.extraire_json(texte)
        commande = self.valider(data)
        cmd_id = self.sauvegarder_offline(commande)
        return cmd_id, commande
