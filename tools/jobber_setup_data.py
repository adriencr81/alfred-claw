"""
tools/jobber_setup_data.py
─────────────────────────────────────────────────────────────────────────────
Script de pré-configuration Jobber pour la démo Alfred.

Crée dans Jobber :
  1. Client  "Clients du Pont"  (avec adresse)
  2. Produit "Panneau Solaire"  dans Products & Services

Prérequis :
  - Chrome lancé avec --remote-debugging-port=9222
  - Connecté à Jobber dans ce Chrome
─────────────────────────────────────────────────────────────────────────────
Usage :
  python tools/jobber_setup_data.py
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from loguru import logger
from playwright.sync_api import sync_playwright, Page

JOBBER_URL  = "https://secure.getjobber.com"
CDP_PORT    = 9222
TIMEOUT     = 20_000

# ── Données à créer ────────────────────────────────────────────────────────────

CLIENT = {
    "prenom":    "Clients",
    "nom":       "du Pont",
    "telephone": "06 00 00 00 00",
    "email":     "contact@clientsdupont.fr",
    "adresse":   "12 Rue du Pont",
    "ville":     "Paris",
    "code_postal": "75001",
}

PRODUIT = {
    "nom":         "Panneau Solaire",
    "description": "Panneau solaire monocristallin 400W",
    "prix_ht":     "250",
    "unite":       "unit",   # "unit", "hour", "day", "flat_rate", "square_foot"
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def connect_chrome() -> tuple:
    """Connexion CDP au vrai Chrome."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            context = browser.contexts[0]
            page    = context.new_page()
            page.set_default_navigation_timeout(60_000)
            return p, browser, context, page
        except Exception as e:
            logger.error(f"❌ Impossible de se connecter à Chrome CDP : {e}")
            logger.error(f"   Lance Chrome avec : --remote-debugging-port={CDP_PORT}")
            sys.exit(1)


def creer_client(page: Page) -> bool:
    """Crée le client dans Jobber."""
    logger.info(f"[Client] Création : {CLIENT['prenom']} {CLIENT['nom']}")

    page.goto(f"{JOBBER_URL}/clients/new", wait_until="domcontentloaded")

    # Attendre le formulaire
    page.get_by_label("First name").wait_for(timeout=TIMEOUT)

    # Prénom / Nom
    page.get_by_label("First name").fill(CLIENT["prenom"])
    page.get_by_label("Last name").fill(CLIENT["nom"])

    # Téléphone
    try:
        page.get_by_label("Phone number").fill(CLIENT["telephone"])
    except Exception:
        logger.warning("[Client] Champ téléphone introuvable — ignoré")

    # Email
    try:
        page.get_by_label("Email").fill(CLIENT["email"])
    except Exception:
        logger.warning("[Client] Champ email introuvable — ignoré")

    # Adresse — chercher le champ adresse (plusieurs labels possibles)
    for label in ("Street 1", "Address", "Street address"):
        try:
            page.get_by_label(label).fill(CLIENT["adresse"])
            break
        except Exception:
            continue

    # Ville
    for label in ("City", "Ville"):
        try:
            page.get_by_label(label).fill(CLIENT["ville"])
            break
        except Exception:
            continue

    # Code postal
    for label in ("Postal / Zip Code", "Zip", "Postal code", "ZIP Code"):
        try:
            page.get_by_label(label, exact=False).fill(CLIENT["code_postal"])
            break
        except Exception:
            continue

    # Sauvegarder
    page.get_by_role("button", name="Save client").click()
    page.wait_for_load_state("domcontentloaded")

    if "/clients/" in page.url and "/new" not in page.url:
        logger.success(f"[Client] ✅ Créé : {page.url}")
        return True
    else:
        logger.warning(f"[Client] ⚠️  URL après save : {page.url} — vérifier manuellement")
        return True  # Peut-être redirigé différemment


def creer_produit(page: Page) -> bool:
    """Crée le produit dans Products & Services."""
    logger.info(f"[Produit] Création : {PRODUIT['nom']}")

    # Jobber Products & Services
    page.goto(f"{JOBBER_URL}/products", wait_until="domcontentloaded")

    # Chercher bouton "New Product or Service" ou "Add"
    try:
        page.get_by_role("link", name="New Product or Service").click()
    except Exception:
        try:
            page.get_by_role("button", name="New Product or Service").click()
        except Exception:
            try:
                page.get_by_role("button", name="Add Product or Service").click()
            except Exception:
                logger.warning("[Produit] Bouton 'New Product' introuvable — essai URL directe")
                page.goto(f"{JOBBER_URL}/products/new", wait_until="domcontentloaded")

    # Attendre le formulaire produit
    time.sleep(1)
    page.wait_for_load_state("domcontentloaded")

    # Nom du produit
    for label in ("Name", "Product name", "Product or Service Name"):
        try:
            field = page.get_by_label(label)
            field.wait_for(timeout=5_000)
            field.fill(PRODUIT["nom"])
            break
        except Exception:
            continue

    # Description
    try:
        page.get_by_label("Description").fill(PRODUIT["description"])
    except Exception:
        logger.warning("[Produit] Champ description introuvable — ignoré")

    # Prix
    for label in ("Unit Price", "Price", "Default Unit Cost"):
        try:
            page.get_by_label(label, exact=False).fill(PRODUIT["prix_ht"])
            break
        except Exception:
            continue

    # Sauvegarder
    for btn_name in ("Save", "Save Product or Service", "Create"):
        try:
            page.get_by_role("button", name=btn_name).click()
            break
        except Exception:
            continue

    page.wait_for_load_state("domcontentloaded")
    logger.success(f"[Produit] ✅ Produit créé/sauvegardé : {page.url}")
    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  JOBBER SETUP DATA — Démo Alfred")
    logger.info("=" * 60)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            logger.success(f"[CDP] Connecté à Chrome sur port {CDP_PORT}")
        except Exception as e:
            logger.error(f"❌ Chrome CDP non disponible : {e}")
            logger.error(f"   Lance : chrome.exe --remote-debugging-port={CDP_PORT}")
            logger.error(f"   Et connecte-toi à Jobber dans ce Chrome")
            sys.exit(1)

        context = browser.contexts[0]
        page    = context.new_page()
        page.set_default_navigation_timeout(60_000)

        # Vérifier session Jobber
        page.goto(f"{JOBBER_URL}/home", wait_until="domcontentloaded")
        if "login" in page.url or "sign_in" in page.url:
            logger.error("❌ Session Jobber expirée — connecte-toi à Jobber dans Chrome d'abord")
            page.close()
            sys.exit(1)

        logger.success(f"[Jobber] Session valide : {page.url}")

        # 1. Créer le client
        ok_client = creer_client(page)

        # 2. Créer le produit
        ok_produit = creer_produit(page)

        logger.info("=" * 60)
        logger.info(f"  Client  : {'✅ OK' if ok_client  else '❌ ÉCHEC'}")
        logger.info(f"  Produit : {'✅ OK' if ok_produit else '❌ ÉCHEC'}")
        logger.info("=" * 60)

        # Laisser la page ouverte pour vérifier
        input("Appuie sur Entrée pour fermer l'onglet...")
        page.close()


if __name__ == "__main__":
    main()
