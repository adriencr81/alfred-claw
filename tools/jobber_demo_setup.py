"""
tools/jobber_demo_setup.py
─────────────────────────────────────────────────────────────────────────────
Setup Jobber pour la démo Alfred (HN / VCs).

Crée dans Jobber :
  1. Client  "Mike Johnson"   → Alfred cherche "Johnson"
  2. Produit "Solar Panel"    → 250.00 USD, automatique dans le devis

Commande vocale démo :
  "Alfred, create a quote — 3 solar panels for Johnson."
  → Jobber : 3 × 250.00 = 750.00 affiché automatiquement

Prérequis :
  - Chrome lancé avec --remote-debugging-port=9222
  - Connecté à Jobber dans ce Chrome
─────────────────────────────────────────────────────────────────────────────
Usage :
  python tools/jobber_demo_setup.py
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import sys
import time
from playwright.sync_api import sync_playwright, Page
from loguru import logger

JOBBER_URL = "https://secure.getjobber.com"
CDP_PORT   = 9222
TIMEOUT    = 20_000

# ── Données démo ───────────────────────────────────────────────────────────────

CLIENT = {
    "first_name": "Mike",
    "last_name":  "Johnson",
    "email":      "mike.johnson@example.com",
    "phone":      "+1 555 000 0001",
}

PRODUIT = {
    "name":        "Solar Panel",
    "description": "Monocrystalline solar panel 400W",
    "price":       "250",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def connect(playwright):
    """Connexion CDP au vrai Chrome."""
    try:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        context = browser.contexts[0]
        page    = context.new_page()
        page.set_default_navigation_timeout(60_000)
        logger.success(f"[CDP] Connecté au Chrome sur port {CDP_PORT}")
        return browser, context, page
    except Exception as e:
        logger.error(f"❌ Chrome CDP non disponible : {e}")
        logger.error(f"   Lance : chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\\Temp\\chrome-debug")
        logger.error(f"   Puis connecte-toi à Jobber dans ce Chrome.")
        sys.exit(1)


def verifier_session(page: Page):
    """Vérifie que la session Jobber est active."""
    page.goto(f"{JOBBER_URL}/home", wait_until="domcontentloaded")
    if "login" in page.url or "sign_in" in page.url:
        logger.error("❌ Session Jobber expirée — reconnecte-toi à Jobber dans Chrome")
        sys.exit(1)
    logger.success(f"[Jobber] Session active : {page.url}")


def creer_client(page: Page) -> bool:
    """Crée le client Mike Johnson."""
    logger.info(f"[Client] Création : {CLIENT['first_name']} {CLIENT['last_name']}")
    page.goto(f"{JOBBER_URL}/clients/new", wait_until="domcontentloaded")

    try:
        page.get_by_label("First name").wait_for(timeout=TIMEOUT)
    except Exception:
        logger.error("[Client] Formulaire client non chargé")
        return False

    page.get_by_label("First name").fill(CLIENT["first_name"])
    page.get_by_label("Last name").fill(CLIENT["last_name"])

    for label in ("Email", "Email address"):
        try:
            page.get_by_label(label).fill(CLIENT["email"])
            break
        except Exception:
            continue

    for label in ("Phone number", "Phone"):
        try:
            page.get_by_label(label).fill(CLIENT["phone"])
            break
        except Exception:
            continue

    try:
        page.get_by_role("button", name="Save client").click()
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        try:
            page.get_by_role("button", name="Save").click()
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            logger.warning("[Client] Bouton Save introuvable")
            return False

    if "/clients/" in page.url and "/new" not in page.url:
        logger.success(f"[Client] ✅ Créé : {page.url}")
        return True
    else:
        logger.warning(f"[Client] ⚠️  URL après save : {page.url}")
        return True


def creer_produit(page: Page) -> bool:
    """Crée le produit Solar Panel à 250."""
    logger.info(f"[Produit] Création : {PRODUIT['name']} @ {PRODUIT['price']}")

    # Naviguer vers la création de produit
    page.goto(f"{JOBBER_URL}/products/new", wait_until="domcontentloaded")
    time.sleep(1)

    # Nom
    for label in ("Name", "Product name", "Product or Service Name"):
        try:
            field = page.get_by_label(label)
            field.wait_for(timeout=8_000)
            field.fill(PRODUIT["name"])
            logger.info(f"[Produit] Nom rempli via label '{label}'")
            break
        except Exception:
            continue
    else:
        logger.error("[Produit] Champ 'Name' introuvable")
        return False

    # Description
    for label in ("Description", "Internal description"):
        try:
            page.get_by_label(label).fill(PRODUIT["description"])
            break
        except Exception:
            continue

    # Prix unitaire
    for label in ("Unit Price", "Price", "Default Unit Cost", "Unit cost"):
        try:
            field = page.get_by_label(label, exact=False)
            field.wait_for(timeout=5_000)
            field.clear()
            field.fill(PRODUIT["price"])
            logger.info(f"[Produit] Prix rempli via label '{label}'")
            break
        except Exception:
            continue

    # Sauvegarder
    for btn_name in ("Save", "Save Product or Service", "Create Product or Service"):
        try:
            page.get_by_role("button", name=btn_name).click()
            page.wait_for_load_state("domcontentloaded")
            logger.success(f"[Produit] ✅ Sauvegardé : {page.url}")
            return True
        except Exception:
            continue

    logger.warning("[Produit] Bouton Save introuvable")
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  JOBBER DEMO SETUP — Alfred HN Demo")
    logger.info("=" * 60)
    logger.info(f"  Client  : {CLIENT['first_name']} {CLIENT['last_name']}")
    logger.info(f"  Produit : {PRODUIT['name']} @ {PRODUIT['price']}")
    logger.info("")
    logger.info("  Commande vocale démo :")
    logger.info('  "Alfred, create a quote — 3 solar panels for Johnson."')
    logger.info("  → Résultat attendu : 3 × 250.00 = 750.00")
    logger.info("=" * 60)

    with sync_playwright() as p:
        browser, context, page = connect(p)
        verifier_session(page)

        ok_client  = creer_client(page)
        ok_produit = creer_produit(page)

        logger.info("=" * 60)
        logger.info(f"  Client  '{CLIENT['first_name']} {CLIENT['last_name']}' : {'✅ OK' if ok_client  else '❌ ÉCHEC'}")
        logger.info(f"  Produit '{PRODUIT['name']}' @ {PRODUIT['price']}      : {'✅ OK' if ok_produit else '❌ ÉCHEC'}")
        logger.info("=" * 60)

        if ok_client and ok_produit:
            logger.success("🎬 Jobber prêt pour la démo !")
            logger.info("   Prochaine étape : python tools/test_pipeline.py")
        else:
            logger.warning("⚠️  Certains éléments n'ont pas pu être créés — vérifier manuellement dans Jobber")

        input("\nAppuie sur Entrée pour fermer...")
        page.close()


if __name__ == "__main__":
    main()
