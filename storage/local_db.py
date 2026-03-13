"""
storage/local_db.py
─────────────────────────────────────────────────────────────────────────────
Base de données SQLite locale.
Stocke toutes les commandes en attente de synchronisation.
Fonctionne 100% offline — aucune dépendance réseau.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

DB_PATH = Path(__file__).parent / "local_db.sqlite"


class LocalDB:
    """Gère la persistance locale des commandes via SQLite."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_schema()

    # ── Initialisation ────────────────────────────────────────────────────────
    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commandes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload     TEXT    NOT NULL,
                    statut      TEXT    NOT NULL DEFAULT 'en_attente',
                    created_at  TEXT    NOT NULL,
                    synced_at   TEXT
                )
                """
            )
        logger.debug(f"[LocalDB] Base initialisée : {self.db_path}")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ── Écriture ──────────────────────────────────────────────────────────────
    def inserer_commande(self, payload: dict[str, Any]) -> int:
        """Insère une commande et retourne son ID local."""
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO commandes (payload, statut, created_at) VALUES (?, ?, ?)",
                (json.dumps(payload, ensure_ascii=False), "en_attente", now),
            )
            cmd_id = cur.lastrowid
        logger.debug(f"[LocalDB] Commande #{cmd_id} insérée")
        return cmd_id

    def marquer_synchronisee(self, cmd_id: int) -> None:
        """Marque une commande comme synchronisée avec le serveur central."""
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE commandes SET statut='synchronisee', synced_at=? WHERE id=?",
                (now, cmd_id),
            )
        logger.debug(f"[LocalDB] Commande #{cmd_id} marquée synchronisée")

    def marquer_erreur(self, cmd_id: int, message: str) -> None:
        """Marque une commande en erreur avec le message d'erreur."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE commandes SET statut=? WHERE id=?",
                (f"erreur: {message[:200]}", cmd_id),
            )

    # ── Lecture ───────────────────────────────────────────────────────────────
    def lire_en_attente(self) -> list[dict[str, Any]]:
        """Retourne toutes les commandes en attente de synchronisation."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, payload FROM commandes WHERE statut='en_attente' ORDER BY id ASC"
            ).fetchall()
        result = [{"id": r[0], "payload": json.loads(r[1])} for r in rows]
        logger.debug(f"[LocalDB] {len(result)} commande(s) en attente")
        return result

    def compter(self) -> dict[str, int]:
        """Retourne le nombre de commandes par statut."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT statut, COUNT(*) FROM commandes GROUP BY statut"
            ).fetchall()
        return {r[0]: r[1] for r in rows}
