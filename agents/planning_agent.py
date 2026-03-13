"""
agents/planning_agent.py
─────────────────────────────────────────────────────────────────────────────
Agent de gestion du planning chantier.
Extrait les informations de dates, équipes, et interventions.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from loguru import logger
from pydantic import BaseModel

from storage.local_db import LocalDB


class InterventionValidee(BaseModel):
    client: str
    type_intervention: str
    date: str           # Format ISO : YYYY-MM-DD
    technicien: str = ""
    duree_heures: float = 4.0
    notes: str = ""


class PlanningAgent:
    """Gère la création et mise à jour des interventions terrain."""

    def __init__(self, db: LocalDB):
        self.db = db
        self.central_url = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")

    def planifier(self, intervention: InterventionValidee) -> bool:
        """Envoie une intervention au serveur central pour planification."""
        logger.info(f"[PlanningAgent] Planification : {intervention.client} le {intervention.date}")

        try:
            response = httpx.post(
                f"{self.central_url}/planifier",
                json=intervention.model_dump(),
                timeout=20.0,
            )
            response.raise_for_status()
            logger.success(f"[PlanningAgent] ✅ Intervention planifiée")
            return True
        except httpx.HTTPError as e:
            logger.error(f"[PlanningAgent] Erreur réseau : {e}")
            # Sauvegarde offline pour retry ultérieur
            self.db.inserer_commande({
                "type": "planning",
                **intervention.model_dump()
            })
            return False
