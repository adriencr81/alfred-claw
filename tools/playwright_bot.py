"""
tools/playwright_bot.py
─────────────────────────────────────────────────────────────────────────────
Robot Playwright pour Jobber (https://secure.getjobber.com).
Utilise les sélecteurs stables via getByLabel() — résistant aux mises à jour
de l'interface Jobber.

Flow principal artisan :
  1. creer_ou_trouver_client()  → /clients/new
  2. creer_job()                → /jobs/new  (title + client + line items)
  3. creer_facture_depuis_job() → depuis la page job

Session : sauvegardée dans storage/jobber_session.json pour éviter
de se reconnecter à chaque appel.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.sync_api import Playwright, sync_playwright, Page, BrowserContext

# ── Configuration ──────────────────────────────────────────────────────────────
JOBBER_URL   = "https://secure.getjobber.com"
SESSION_FILE = Path("storage/jobber_session.json")
HEADLESS     = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

TIMEOUT_COURT = 8_000   # ms — pour les éléments rapides
TIMEOUT_LONG  = 20_000  # ms — pour les navigations


class JobberBot:
    """Automatise la saisie dans Jobber via Playwright."""

    # ── Authentification & session ─────────────────────────────────────────────

    def _get_page(self, playwright: Playwright) -> tuple[Any, BrowserContext, Page]:
        """
        Retourne une page authentifiée via la session sauvegardée.
        Si la session est absente ou expirée, lève une erreur claire.
        → Lancer tools/jobber_setup_session.py pour initialiser la session.
        """
        if not SESSION_FILE.exists():
            raise RuntimeError(
                "Session Jobber introuvable. "
                "Lance d'abord : python tools/jobber_setup_session.py"
            )

        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context(storage_state=str(SESSION_FILE))
        page    = context.new_page()

        # Vérifier que la session est toujours valide
        page.goto(f"{JOBBER_URL}/home", wait_until="networkidle")

        if "login" in page.url or "sign_in" in page.url:
            browser.close()
            SESSION_FILE.unlink(missing_ok=True)
            raise RuntimeError(
                "Session Jobber expirée. "
                "Relance : python tools/jobber_setup_session.py"
            )

        logger.debug(f"[Jobber] Session valide — URL: {page.url}")
        return browser, context, page

    # ── Client ─────────────────────────────────────────────────────────────────

    def creer_client(self, data: dict[str, Any]) -> bool:
        """
        Crée un nouveau client dans Jobber.

        data attendu :
          - client      : "Prénom Nom" (séparé automatiquement)
          - telephone   : optionnel
          - email       : optionnel
        """
        nom_complet = data.get("client", "Client inconnu")
        parties     = nom_complet.strip().split(" ", 1)
        prenom      = parties[0]
        nom         = parties[1] if len(parties) > 1 else ""

        logger.info(f"[Jobber] Création client : {nom_complet}")

        try:
            with sync_playwright() as p:
                browser, context, page = self._get_page(p)

                page.goto(f"{JOBBER_URL}/clients/new", wait_until="networkidle")

                # Prénom / Nom
                page.get_by_label("First name").fill(prenom)
                if nom:
                    page.get_by_label("Last name").fill(nom)

                # Téléphone et email (optionnels)
                if data.get("telephone"):
                    page.get_by_label("Phone number").fill(data["telephone"])
                if data.get("email"):
                    page.get_by_label("Email").fill(data["email"])

                # Sauvegarde
                page.get_by_role("button", name="Save client").click()
                page.wait_for_load_state("networkidle")

                logger.success(f"[Jobber] ✅ Client créé : {nom_complet}")
                context.storage_state(path=str(SESSION_FILE))
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[Jobber] ❌ Erreur création client : {e}")
            return False

    def _chercher_client(self, page: Page, nom_client: str) -> bool:
        """
        Cherche et sélectionne un client dans l'autocomplete Jobber.
        Retourne True si trouvé, False sinon.
        """
        champ_client = page.get_by_label("Select a client")
        champ_client.click()
        champ_client.fill(nom_client)

        # Attendre le dropdown
        try:
            suggestion = page.get_by_role("option").first
            suggestion.wait_for(timeout=TIMEOUT_COURT)
            suggestion.click()
            logger.debug(f"[Jobber] Client sélectionné : {nom_client}")
            return True
        except Exception:
            # Si pas de suggestion → client n'existe pas encore
            logger.warning(f"[Jobber] Client '{nom_client}' non trouvé dans Jobber")
            return False

    # ── Job ────────────────────────────────────────────────────────────────────

    def creer_job(self, data: dict[str, Any]) -> str | None:
        """
        Crée un nouveau Job dans Jobber avec ses lignes (matériaux + main d'œuvre).

        data attendu :
          - client           : nom du client
          - item             : description principale
          - quantite         : quantité
          - prix_unitaire_ht : prix unitaire (après enrichissement GPT)
          - reference_produit: nom produit enrichi (optionnel)
          - notes            : notes internes (optionnel)
          - lignes           : list de dicts [{nom, quantite, prix, description}]
                               (optionnel — si absent, une seule ligne créée)

        Retourne l'URL du job créé, ou None en cas d'erreur.
        """
        client    = data.get("client", "")
        titre_job = data.get("item", "Intervention")
        logger.info(f"[Jobber] Création job : '{titre_job}' pour {client}")

        try:
            with sync_playwright() as p:
                browser, context, page = self._get_page(p)

                page.goto(f"{JOBBER_URL}/jobs/new", wait_until="networkidle")

                # ── Titre du job ───────────────────────────────────────────────
                page.get_by_label("Title").fill(titre_job)

                # ── Client (autocomplete) ──────────────────────────────────────
                client_trouve = self._chercher_client(page, client)
                if not client_trouve:
                    # Créer le client dans un onglet séparé du même contexte
                    logger.info(f"[Jobber] Création du client '{client}' à la volée")
                    parties = client.strip().split(" ", 1)
                    client_page = context.new_page()
                    client_page.goto(f"{JOBBER_URL}/clients/new", wait_until="networkidle")
                    client_page.get_by_label("First name").fill(parties[0])
                    if len(parties) > 1:
                        client_page.get_by_label("Last name").fill(parties[1])
                    client_page.get_by_role("button", name="Save client").click()
                    client_page.wait_for_load_state("networkidle")
                    client_page.close()
                    logger.success(f"[Jobber] ✅ Client '{client}' créé")

                    # Revenir au formulaire job et rechercher le client nouvellement créé
                    page.goto(f"{JOBBER_URL}/jobs/new", wait_until="networkidle")
                    page.get_by_label("Title").fill(titre_job)
                    self._chercher_client(page, client)

                # ── Lignes (line items) ────────────────────────────────────────
                lignes = data.get("lignes") or [self._ligne_depuis_data(data)]

                for idx, ligne in enumerate(lignes):
                    if idx > 0:
                        # Ajouter une ligne supplémentaire
                        page.get_by_role("button", name="Add Line Item").click()
                        time.sleep(0.5)

                    # Remplir la nth ligne
                    page.get_by_label("Name").nth(idx).fill(ligne["nom"])
                    page.get_by_label("Quantity").nth(idx).triple_click()
                    page.get_by_label("Quantity").nth(idx).fill(str(ligne["quantite"]))

                    if ligne.get("prix", 0) > 0:
                        page.get_by_label("Unit price").nth(idx).triple_click()
                        page.get_by_label("Unit price").nth(idx).fill(str(ligne["prix"]))

                    if ligne.get("description"):
                        page.get_by_label("Description").nth(idx).fill(ligne["description"])

                # ── Sauvegarde ─────────────────────────────────────────────────
                page.get_by_role("button", name="Save Job").click()
                page.wait_for_load_state("networkidle")

                job_url = page.url
                logger.success(f"[Jobber] ✅ Job créé : {job_url}")

                context.storage_state(path=str(SESSION_FILE))
                browser.close()
                return job_url

        except Exception as e:
            logger.error(f"[Jobber] ❌ Erreur création job : {e}")
            return None

    def _ligne_depuis_data(self, data: dict[str, Any]) -> dict:
        """Construit une ligne à partir du dict de commande standard Alfred."""
        return {
            "nom":         data.get("reference_produit") or data.get("item", ""),
            "quantite":    data.get("quantite", 1),
            "prix":        data.get("prix_unitaire_ht", 0),
            "description": data.get("notes", ""),
        }

    # ── Facture depuis un Job ──────────────────────────────────────────────────

    def creer_facture_depuis_job(self, job_url: str) -> bool:
        """
        Navigue vers un job existant et crée la facture associée.
        Jobber génère la facture à partir des line items du job.
        """
        logger.info(f"[Jobber] Création facture depuis job : {job_url}")

        try:
            with sync_playwright() as p:
                browser, context, page = self._get_page(p)

                page.goto(job_url, wait_until="networkidle")

                # Chercher le bouton "Create Invoice" dans le menu du job
                try:
                    page.get_by_role("button", name="Create Invoice").click()
                except Exception:
                    # Parfois dans un menu déroulant
                    page.get_by_role("button", name="More actions").click()
                    page.get_by_role("menuitem", name="Create Invoice").click()

                page.wait_for_load_state("networkidle")

                # Confirmer si une modale apparaît
                try:
                    page.get_by_role("button", name="Create Invoice").click(timeout=3_000)
                except Exception:
                    pass  # Pas de modale de confirmation

                page.wait_for_load_state("networkidle")
                facture_url = page.url

                logger.success(f"[Jobber] ✅ Facture créée : {facture_url}")
                context.storage_state(path=str(SESSION_FILE))
                browser.close()
                return True

        except Exception as e:
            logger.error(f"[Jobber] ❌ Erreur création facture : {e}")
            return False

    # ── Point d'entrée principal (appelé par FacturationAgent) ─────────────────

    def traiter(self, data: dict[str, Any]) -> bool:
        """
        Dispatch selon l'action demandée.
        Compatible avec l'interface attendue par FacturationAgent.

        Actions supportées :
          - ajouter_devis     → crée un Job
          - creer_facture     → crée un Job + facture
          - modifier_devis    → crée un Job (ajout de ligne)
          - ajouter_commande  → crée un Job
        """
        action = data.get("action", "ajouter_devis")
        logger.info(f"[Jobber] Action : {action} — client : {data.get('client')}")

        if action in ("ajouter_devis", "modifier_devis", "ajouter_commande"):
            job_url = self.creer_job(data)
            return job_url is not None

        elif action == "creer_facture":
            job_url = self.creer_job(data)
            if job_url:
                return self.creer_facture_depuis_job(job_url)
            return False

        else:
            logger.warning(f"[Jobber] Action inconnue : {action}")
            return False

    # ── Alias rétrocompatibilité (ancienne interface) ──────────────────────────

    def creer_devis(self, data: dict[str, Any]) -> bool:
        return self.creer_job(data) is not None

    def creer_facture(self, data: dict[str, Any]) -> bool:
        job_url = self.creer_job(data)
        if job_url:
            return self.creer_facture_depuis_job(job_url)
        return False

    def modifier_devis(self, data: dict[str, Any]) -> bool:
        return self.creer_job(data) is not None

    def creer_commande(self, data: dict[str, Any]) -> bool:
        return self.creer_job(data) is not None


# Alias de rétrocompatibilité — FacturationAgent importe PlaywrightBot
PlaywrightBot = JobberBot
