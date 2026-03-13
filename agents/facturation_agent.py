"""
agents/facturation_agent.py
─────────────────────────────────────────────────────────────────────────────
Agent de facturation.
Reçoit une CommandeValidee, l'envoie au serveur central pour enrichissement,
puis déclenche l'automatisation dans le logiciel de facturation.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from core.openclaw_engine import CommandeValidee
from storage.local_db import LocalDB
from tools.playwright_bot import PlaywrightBot


# ─── Modèle enrichi retourné par GPT central ─────────────────────────────────
class CommandeEnrichie(BaseModel):
    client: str
    item: str
    quantite: float
    action: str
    notes: str = ""
    prix_unitaire_ht: float = Field(default=0.0, ge=0)
    tva_pct: float = Field(default=20.0, ge=0)
    reference_produit: str = ""
    alerte: str = ""

    @property
    def prix_ttc(self) -> float:
        return round(self.quantite * self.prix_unitaire_ht * (1 + self.tva_pct / 100), 2)


# ─── Agent ────────────────────────────────────────────────────────────────────
class FacturationAgent:
    """
    Pipeline complet :
    CommandeValidee  →  enrichissement GPT  →  injection logiciel facturation
    """

    def __init__(self, db: LocalDB):
        self.db = db
        self.central_url = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")
        self.bot = PlaywrightBot()

    # ── Étape 1 : Enrichissement via GPT central ─────────────────────────────
    def enrichir(self, commande: CommandeValidee) -> CommandeEnrichie:
        """Envoie la commande au serveur central (GPT) pour enrichissement."""
        logger.info(f"[FacturationAgent] Enrichissement de : {commande.client}")

        try:
            response = httpx.post(
                f"{self.central_url}/enrichir",
                json=commande.model_dump(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            enrichie = CommandeEnrichie(**data)

            if enrichie.alerte:
                logger.warning(f"[FacturationAgent] ⚠️ Alerte GPT : {enrichie.alerte}")

            logger.success(f"[FacturationAgent] Enrichissement OK — Prix TTC : {enrichie.prix_ttc}€")
            return enrichie

        except httpx.HTTPError as e:
            logger.error(f"[FacturationAgent] Serveur central inaccessible : {e}")
            logger.info("[FacturationAgent] Utilisation des données locales sans enrichissement")
            # Fallback : utilisation des données validées localement
            return CommandeEnrichie(**commande.model_dump())

    # ── Étape 2 : Injection dans le logiciel de facturation ───────────────────
    def injecter(self, commande: CommandeEnrichie) -> bool:
        """Lance Playwright pour créer le devis/facture dans le logiciel."""
        logger.info(f"[FacturationAgent] Injection — action : {commande.action}")

        action_map = {
            "ajouter_devis":    self.bot.creer_devis,
            "creer_facture":    self.bot.creer_facture,
            "modifier_devis":   self.bot.modifier_devis,
            "ajouter_commande": self.bot.creer_commande,
        }

        handler = action_map.get(commande.action)
        if handler is None:
            logger.error(f"[FacturationAgent] Action inconnue : {commande.action}")
            return False

        return handler(commande.model_dump())

    # ── Pipeline complet ──────────────────────────────────────────────────────
    def traiter(self, cmd_id: int, commande: CommandeValidee) -> bool:
        """
        Orchestre : enrichissement + injection.
        Met à jour le statut en DB selon le résultat.
        """
        try:
            enrichie = self.enrichir(commande)
            succes = self.injecter(enrichie)

            if succes:
                self.db.marquer_synchronisee(cmd_id)
                logger.success(f"[FacturationAgent] ✅ Commande #{cmd_id} traitée")
            else:
                self.db.marquer_erreur(cmd_id, "Injection échouée")
                logger.error(f"[FacturationAgent] ❌ Injection échouée pour #{cmd_id}")

            return succes

        except Exception as e:
            self.db.marquer_erreur(cmd_id, str(e))
            logger.exception(f"[FacturationAgent] Exception pour #{cmd_id} : {e}")
            return False
