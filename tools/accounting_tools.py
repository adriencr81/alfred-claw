"""
tools/accounting_tools.py
─────────────────────────────────────────────────────────────────────────────
Connecteurs API REST pour les logiciels de facturation courants.
Alternative à Playwright quand une API officielle est disponible.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger


class FacturationAPI:
    """
    Connecteur générique REST vers le logiciel de facturation.
    Utilise l'API REST si disponible (plus robuste que Playwright).
    """

    def __init__(self):
        self.base_url = os.getenv("FACTURATION_URL", "http://localhost:3000")
        self.token = os.getenv("FACTURATION_API_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def creer_devis_api(self, data: dict[str, Any]) -> dict | None:
        """Crée un devis via l'API REST."""
        payload = {
            "client_name": data["client"],
            "lines": [
                {
                    "description": data.get("reference_produit") or data["item"],
                    "quantity": data["quantite"],
                    "unit_price": data.get("prix_unitaire_ht", 0),
                    "tax_rate": data.get("tva_pct", 20),
                }
            ],
            "notes": data.get("notes", ""),
        }

        try:
            r = httpx.post(
                f"{self.base_url}/api/v1/quotes",
                json=payload,
                headers=self.headers,
                timeout=15.0,
            )
            r.raise_for_status()
            result = r.json()
            logger.success(f"[FacturationAPI] Devis créé : ID {result.get('id')}")
            return result
        except httpx.HTTPError as e:
            logger.error(f"[FacturationAPI] Erreur API : {e}")
            return None

    def creer_facture_api(self, data: dict[str, Any]) -> dict | None:
        """Crée une facture via l'API REST."""
        payload = {
            "client_name": data["client"],
            "lines": [
                {
                    "description": data.get("reference_produit") or data["item"],
                    "quantity": data["quantite"],
                    "unit_price": data.get("prix_unitaire_ht", 0),
                    "tax_rate": data.get("tva_pct", 20),
                }
            ],
        }

        try:
            r = httpx.post(
                f"{self.base_url}/api/v1/invoices",
                json=payload,
                headers=self.headers,
                timeout=15.0,
            )
            r.raise_for_status()
            result = r.json()
            logger.success(f"[FacturationAPI] Facture créée : ID {result.get('id')}")
            return result
        except httpx.HTTPError as e:
            logger.error(f"[FacturationAPI] Erreur API : {e}")
            return None


class InventoryAPI:
    """Connecteur pour gestion du stock matériel."""

    def __init__(self):
        self.base_url = os.getenv("INVENTORY_URL", "http://localhost:3001")
        self.token = os.getenv("INVENTORY_API_TOKEN", "")

    def verifier_stock(self, reference: str) -> dict | None:
        """Vérifie la disponibilité d'un article en stock."""
        try:
            r = httpx.get(
                f"{self.base_url}/api/stock/{reference}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return None

    def reserver_stock(self, reference: str, quantite: float) -> bool:
        """Réserve une quantité d'un article."""
        try:
            r = httpx.post(
                f"{self.base_url}/api/stock/reserver",
                json={"reference": reference, "quantite": quantite},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10.0,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"[InventoryAPI] Erreur réservation : {e}")
            return False
