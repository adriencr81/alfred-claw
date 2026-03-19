"""
agents/chrono_agent.py
─────────────────────────────────────────────────────────────────────────────
Chronomètre de chantier vocal.
Démarre/arrête les sessions de travail et génère la commande de facturation
des heures de main d'œuvre.

Commandes vocales :
  "Alfred, début chantier Johnson"  → demarrer("Johnson")
  "Alfred, fin chantier"            → arreter()
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from loguru import logger

from storage.local_db import LocalDB


class ChronoAgent:
    """Gère les chronos de chantier et calcule les heures de MO."""

    def __init__(self, db: LocalDB):
        self.db = db

    def demarrer(self, client: str) -> str:
        """Démarre un chrono pour le client donné. Retourne un message de confirmation."""
        actif = self.db.chrono_actif()
        if actif:
            logger.warning(f"[Chrono] Chrono déjà en cours pour {actif['client']}")
            return f"Chrono déjà actif pour {actif['client']}. Dis 'fin chantier' d'abord."

        self.db.demarrer_chrono(client)
        logger.success(f"[Chrono] ▶ Début chantier {client}")
        return f"Chrono démarré pour {client}."

    def arreter(self) -> tuple[dict | None, dict | None]:
        """
        Arrête le chrono actif et calcule les heures.
        Retourne (chrono_data, payload_facturation) ou (None, None) si aucun chrono actif.
        Le payload_facturation est une commande prête pour la sync vers Jobber.
        """
        chrono = self.db.arreter_chrono()
        if not chrono:
            logger.warning("[Chrono] Aucun chrono actif à arrêter")
            return None, None

        duree_h = chrono["duree_h"]
        client = chrono["client"]
        logger.success(f"[Chrono] ⏹ Fin chantier {client} — {duree_h:.2f}h")

        payload = {
            "client": client,
            "item": "main d'oeuvre",
            "quantite": duree_h,
            "action": "creer_facture",
            "notes": f"{duree_h:.2f}h de main d'oeuvre — chantier {client}",
        }
        return chrono, payload
