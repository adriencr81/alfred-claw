"""
tools/jobber_setup_session.py
─────────────────────────────────────────────────────────────────────────────
Script one-shot pour initialiser la session Jobber.

Stratégie : connecte Playwright à ton Chrome déjà ouvert (CDP).
Google OAuth fonctionne car c'est ton vrai Chrome, pas un browser automatisé.

ÉTAPES :
  1. Ferme TOUS les onglets Chrome ouverts (ou utilise un profil séparé)
  2. Lance Chrome avec le port de debug :
       "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
  3. Dans ce Chrome, va sur https://secure.getjobber.com et connecte-toi (MFA inclus)
  4. Lance ce script :
       python tools/jobber_setup_session.py
  5. Le script sauvegarde les cookies → storage/jobber_session.json
─────────────────────────────────────────────────────────────────────────────
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from loguru import logger

SESSION_FILE   = Path("storage/jobber_session.json")
JOBBER_URL     = "https://secure.getjobber.com"
CDP_PORT       = 9222


def setup_session() -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  SETUP SESSION JOBBER (via Chrome CDP)")
    logger.info("=" * 60)
    logger.info("Prérequis :")
    logger.info('  1. Chrome lancé avec : --remote-debugging-port=9222')
    logger.info('  2. Connecté à Jobber dans ce Chrome (MFA fait)')
    logger.info("=" * 60)

    input("Appuie sur Entrée quand tu es connecté à Jobber dans Chrome...")

    with sync_playwright() as p:
        try:
            # Connexion au Chrome existant via CDP
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            logger.info(f"[Setup] Connecté à Chrome sur le port {CDP_PORT}")
        except Exception as e:
            logger.error(f"❌ Impossible de se connecter à Chrome : {e}")
            logger.error(f"   Vérifie que Chrome tourne avec --remote-debugging-port={CDP_PORT}")
            logger.error(f"   Test : ouvre http://127.0.0.1:{CDP_PORT}/json dans ton browser")
            return

        # Récupérer le contexte existant (avec la session Jobber)
        contexts = browser.contexts
        if not contexts:
            logger.error("❌ Aucun contexte trouvé dans Chrome.")
            return

        context = contexts[0]

        # Vérifier qu'on est bien sur Jobber
        pages = context.pages
        jobber_page = None
        for page in pages:
            if "getjobber.com" in page.url:
                jobber_page = page
                break

        if not jobber_page:
            logger.warning("⚠️  Aucun onglet Jobber trouvé — assure-toi d'être connecté")
            logger.warning("   Onglets ouverts :")
            for page in pages:
                logger.warning(f"   - {page.url}")
            return

        logger.info(f"[Setup] Onglet Jobber trouvé : {jobber_page.url}")

        # Sauvegarder la session
        context.storage_state(path=str(SESSION_FILE))
        logger.success(f"✅ Session sauvegardée dans {SESSION_FILE}")
        logger.info("Alfred utilisera cette session pour toutes les actions Jobber.")


if __name__ == "__main__":
    setup_session()
