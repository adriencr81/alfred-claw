"""
tools/jobber_setup_session.py
─────────────────────────────────────────────────────────────────────────────
Script one-shot pour initialiser la session Jobber.

À lancer UNE SEULE FOIS (ou quand la session expire) :
  python tools/jobber_setup_session.py

Le browser s'ouvre en mode visible. Tu te connectes manuellement
(email + mot de passe + MFA). Dès que le dashboard est chargé,
la session est sauvegardée dans storage/jobber_session.json.

Tous les appels Playwright suivants réutilisent cette session
sans repasser par le login.
─────────────────────────────────────────────────────────────────────────────
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from loguru import logger

SESSION_FILE = Path("storage/jobber_session.json")
JOBBER_URL   = "https://secure.getjobber.com"


def setup_session() -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  SETUP SESSION JOBBER")
    logger.info("=" * 60)
    logger.info("Le navigateur va s'ouvrir.")
    logger.info("→ Connecte-toi manuellement (email + MFA)")
    logger.info("→ Attends que le dashboard soit chargé")
    logger.info("→ Le script sauvegarde la session automatiquement")
    logger.info("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page    = context.new_page()

        # Ouvrir la page de login
        page.goto(f"{JOBBER_URL}/login")

        # Attendre que l'utilisateur arrive sur le dashboard
        # (peu importe le temps que prend le MFA)
        logger.info("En attente de ta connexion... (timeout : 5 minutes)")
        page.wait_for_url(
            f"{JOBBER_URL}/**",
            wait_until="networkidle",
            timeout=300_000,  # 5 minutes
        )

        # Vérifier qu'on est bien connecté (pas redirigé vers login)
        if "login" in page.url or "sign_in" in page.url:
            logger.error("❌ Connexion échouée ou timeout. Relance le script.")
            browser.close()
            return

        # Sauvegarder la session
        context.storage_state(path=str(SESSION_FILE))
        logger.success(f"✅ Session sauvegardée dans {SESSION_FILE}")
        logger.info("Tu peux fermer le navigateur.")
        logger.info("Alfred utilisera cette session pour toutes les actions Jobber.")

        input("\nAppuie sur Entrée pour fermer le navigateur...")
        browser.close()


if __name__ == "__main__":
    setup_session()
