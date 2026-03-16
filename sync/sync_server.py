"""
sync/sync_server.py
─────────────────────────────────────────────────────────────────────────────
Gestionnaire de synchronisation offline → cloud.
- Tourne en boucle en arrière-plan.
- Récupère les commandes en attente dans la DB locale.
- Les envoie au serveur central (GPT) dès que le réseau est disponible.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import time
import threading

import httpx
from loguru import logger

from storage.local_db import LocalDB
from agents.facturation_agent import FacturationAgent
from core.openclaw_engine import CommandeValidee


SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "30"))


class SyncManager:
    """
    Gère la synchronisation en arrière-plan entre le Raspberry Pi et le cloud.
    Respecte le pattern offline-first :
      1. La commande est TOUJOURS sauvegardée localement en premier.
      2. La synchro avec le cloud est tentée à intervalle régulier.
      3. En cas d'échec réseau, la commande reste en attente (pas de perte).
    """

    def __init__(self, db: LocalDB, agent: FacturationAgent):
        self.db = db
        self.agent = agent
        self._stop = threading.Event()

    # ── Vérification connectivité ─────────────────────────────────────────────
    def _est_connecte(self) -> bool:
        """Teste si le serveur central est accessible."""
        central_url = os.getenv("CENTRAL_SERVER_URL", "http://localhost:8000")
        try:
            httpx.get(f"{central_url}/health", timeout=5.0)
            return True
        except httpx.HTTPError:
            return False

    # ── Cycle de synchronisation ──────────────────────────────────────────────
    def _cycle_sync(self) -> None:
        """Un cycle complet de synchronisation."""
        if not self._est_connecte():
            logger.debug(f"[Sync] Serveur central non accessible — retry dans {SYNC_INTERVAL}s")
            return

        commandes = self.db.lire_en_attente()
        if not commandes:
            logger.debug("[Sync] Aucune commande en attente")
            return

        logger.info(f"[Sync] {len(commandes)} commande(s) à synchroniser")

        for item in commandes:
            cmd_id = item["id"]
            payload = item["payload"]

            try:
                # Reconstruction de la CommandeValidee depuis le payload stocké
                commande = CommandeValidee(**payload)
                succes = self.agent.traiter(cmd_id, commande)

                if succes:
                    logger.success(f"[Sync] ✅ Commande #{cmd_id} synchronisée")
                else:
                    logger.warning(f"[Sync] ⚠️ Commande #{cmd_id} en erreur — sera retentée")

            except Exception as e:
                logger.error(f"[Sync] Erreur pour commande #{cmd_id} : {e}")
                self.db.marquer_erreur(cmd_id, str(e))

    # ── Boucle principale ─────────────────────────────────────────────────────
    def demarrer(self) -> None:
        """Lance la boucle de synchronisation en arrière-plan."""
        logger.info(f"[Sync] Démarrage (intervalle : {SYNC_INTERVAL}s)")

        while not self._stop.is_set():
            try:
                self._cycle_sync()
            except Exception as e:
                logger.exception(f"[Sync] Erreur inattendue : {e}")

            self._stop.wait(timeout=SYNC_INTERVAL)

    def arreter(self) -> None:
        """Arrête proprement la boucle de synchronisation."""
        logger.info("[Sync] Arrêt demandé")
        self._stop.set()

    def demarrer_en_thread(self) -> threading.Thread:
        """Lance le SyncManager dans un thread daemon."""
        t = threading.Thread(target=self.demarrer, daemon=True, name="SyncManager")
        t.start()
        logger.info("[Sync] Thread de synchronisation démarré")
        return t
