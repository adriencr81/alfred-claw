"""
tools/playwright_bot.py
─────────────────────────────────────────────────────────────────────────────
Robot Playwright qui automatise les actions dans le logiciel de facturation.
Agit comme un humain devant l'écran : clique, remplit les formulaires,
valide les saisies.

⚙️  Adapter les sélecteurs CSS aux éléments de VOTRE logiciel de facturation.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from playwright.sync_api import Playwright, sync_playwright, Page, Browser


FACTURATION_URL  = os.getenv("FACTURATION_URL", "http://localhost:3000")
FACTURATION_USER = os.getenv("FACTURATION_USER", "admin")
FACTURATION_PASS = os.getenv("FACTURATION_PASS", "password")


class PlaywrightBot:
    """Automatise la saisie dans le logiciel de facturation."""

    # ── Connexion et session ──────────────────────────────────────────────────
    def _get_page(self, playwright: Playwright) -> tuple[Browser, Page]:
        """Lance le navigateur et se connecte au logiciel."""
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        # Connexion au logiciel
        page.goto(f"{FACTURATION_URL}/login")
        page.fill("#username", FACTURATION_USER)
        page.fill("#password", FACTURATION_PASS)
        page.click("#btn-login")
        page.wait_for_url(f"{FACTURATION_URL}/dashboard", timeout=10_000)

        logger.debug("[PlaywrightBot] Connecté au logiciel de facturation")
        return browser, page

    # ── Création d'un devis ───────────────────────────────────────────────────
    def creer_devis(self, data: dict[str, Any]) -> bool:
        """
        Crée un nouveau devis dans le logiciel.
        ⚙️  Adapter les sélecteurs à votre interface.
        """
        logger.info(f"[PlaywrightBot] Création devis pour {data['client']}")

        try:
            with sync_playwright() as p:
                browser, page = self._get_page(p)

                # Navigation vers nouveau devis
                page.goto(f"{FACTURATION_URL}/devis/nouveau")

                # ── Saisie client ──────────────────────────────────────────
                # ⚙️  Remplacer "#client-search" par le bon sélecteur
                page.fill("#client-search", data["client"])
                page.click(f"text={data['client']}")         # Sélection dans dropdown

                # ── Ajout ligne produit ────────────────────────────────────
                page.click("#btn-ajouter-ligne")
                page.fill("#article-input", data.get("reference_produit") or data["item"])
                page.fill("#quantite-input", str(data["quantite"]))

                # Prix si disponible
                if data.get("prix_unitaire_ht", 0) > 0:
                    page.fill("#prix-input", str(data["prix_unitaire_ht"]))

                # Notes
                if data.get("notes"):
                    page.fill("#notes-textarea", data["notes"])

                # ── Sauvegarde ────────────────────────────────────────────
                page.click("#btn-sauvegarder")
                page.wait_for_selector(".toast-success", timeout=5_000)

                logger.success(f"[PlaywrightBot] ✅ Devis créé pour {data['client']}")
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[PlaywrightBot] Erreur création devis : {e}")
            return False

    # ── Création d'une facture ────────────────────────────────────────────────
    def creer_facture(self, data: dict[str, Any]) -> bool:
        """Crée une facture directe."""
        logger.info(f"[PlaywrightBot] Création facture pour {data['client']}")

        try:
            with sync_playwright() as p:
                browser, page = self._get_page(p)

                page.goto(f"{FACTURATION_URL}/factures/nouvelle")
                page.fill("#client-search", data["client"])
                page.click(f"text={data['client']}")
                page.click("#btn-ajouter-ligne")
                page.fill("#article-input", data.get("reference_produit") or data["item"])
                page.fill("#quantite-input", str(data["quantite"]))

                if data.get("prix_unitaire_ht", 0) > 0:
                    page.fill("#prix-input", str(data["prix_unitaire_ht"]))

                page.click("#btn-sauvegarder")
                page.wait_for_selector(".toast-success", timeout=5_000)

                logger.success(f"[PlaywrightBot] ✅ Facture créée pour {data['client']}")
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[PlaywrightBot] Erreur création facture : {e}")
            return False

    # ── Modification d'un devis ───────────────────────────────────────────────
    def modifier_devis(self, data: dict[str, Any]) -> bool:
        """Modifie un devis existant (recherche par client)."""
        logger.info(f"[PlaywrightBot] Modification devis pour {data['client']}")

        try:
            with sync_playwright() as p:
                browser, page = self._get_page(p)

                # Recherche du dernier devis du client
                page.goto(f"{FACTURATION_URL}/devis")
                page.fill("#search-client", data["client"])
                page.click(".devis-result:first-child")

                # Ajout d'une nouvelle ligne
                page.click("#btn-ajouter-ligne")
                page.fill("#article-input", data["item"])
                page.fill("#quantite-input", str(data["quantite"]))
                page.click("#btn-sauvegarder")
                page.wait_for_selector(".toast-success", timeout=5_000)

                logger.success(f"[PlaywrightBot] ✅ Devis modifié pour {data['client']}")
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[PlaywrightBot] Erreur modification devis : {e}")
            return False

    # ── Création d'une commande fournisseur ───────────────────────────────────
    def creer_commande(self, data: dict[str, Any]) -> bool:
        """Crée une commande matériel."""
        logger.info(f"[PlaywrightBot] Commande matériel : {data['item']} x{data['quantite']}")

        try:
            with sync_playwright() as p:
                browser, page = self._get_page(p)

                page.goto(f"{FACTURATION_URL}/commandes/nouvelle")
                page.fill("#client-ref", data["client"])
                page.fill("#article-input", data["item"])
                page.fill("#quantite-input", str(data["quantite"]))

                if data.get("notes"):
                    page.fill("#notes-textarea", data["notes"])

                page.click("#btn-sauvegarder")
                page.wait_for_selector(".toast-success", timeout=5_000)

                logger.success(f"[PlaywrightBot] ✅ Commande créée")
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[PlaywrightBot] Erreur création commande : {e}")
            return False
