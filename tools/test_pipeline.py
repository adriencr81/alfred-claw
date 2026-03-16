"""
tools/test_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Script de test du pipeline complet Alfred sur PC :
  commande JSON → enrichissement GPT (serveur local) → Jobber via Playwright

Usage :
  python tools/test_pipeline.py

Prérequis :
  - Le serveur uvicorn tourne : uvicorn server.main:app --host 0.0.0.0 --port 8000
  - La session Jobber est capturée : storage/jobber_session.json
─────────────────────────────────────────────────────────────────────────────
"""

import json
import sys
from pathlib import Path

import httpx
from loguru import logger

# ── Ajouter la racine du projet au path ───────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.playwright_bot import JobberBot

# ── Configuration ─────────────────────────────────────────────────────────────
SERVER_URL   = "http://127.0.0.1:8000"
SESSION_FILE = ROOT / "storage" / "jobber_session.json"

# ── Données simulant la commande Pi (id=1 dans SQLite) ────────────────────────
COMMANDE_PI = {
    "client":   "clients du pont",
    "item":     "panneau solaire",
    "quantite": 3.0,
    "action":   "ajouter_devis",
    "notes":    "",
}


def check_server() -> bool:
    try:
        r = httpx.get(f"{SERVER_URL}/health", timeout=5)
        r.raise_for_status()
        logger.success(f"[Test] ✅ Serveur OK : {r.json()}")
        return True
    except Exception as e:
        logger.error(f"[Test] ❌ Serveur inaccessible : {e}")
        logger.error("   Lance d'abord : uvicorn server.main:app --host 0.0.0.0 --port 8000")
        return False


def check_session() -> bool:
    if SESSION_FILE.exists():
        logger.success(f"[Test] ✅ Session Jobber trouvée : {SESSION_FILE}")
        return True
    logger.error(f"[Test] ❌ Session manquante : {SESSION_FILE}")
    logger.error("   Lance d'abord : python tools/jobber_setup_session.py")
    return False


def enrichir(commande: dict) -> dict | None:
    logger.info(f"[Test] Enrichissement GPT pour : {commande['client']} — {commande['item']}")
    try:
        r = httpx.post(f"{SERVER_URL}/enrichir", json=commande, timeout=30)
        r.raise_for_status()
        enrichie = r.json()
        logger.success(
            f"[Test] ✅ Enrichissement OK\n"
            f"   → référence   : {enrichie.get('reference_produit')}\n"
            f"   → prix HT     : {enrichie.get('prix_unitaire_ht')}€\n"
            f"   → TVA         : {enrichie.get('tva_pct')}%\n"
            f"   → alerte      : {enrichie.get('alerte') or 'aucune'}"
        )
        return enrichie
    except Exception as e:
        logger.error(f"[Test] ❌ Erreur enrichissement : {e}")
        return None


def injecter_jobber(enrichie: dict) -> bool:
    logger.info(f"[Test] Injection Jobber — action : {enrichie.get('action')}")
    bot = JobberBot()
    succes = bot.traiter(enrichie)
    if succes:
        logger.success("[Test] ✅ Job créé dans Jobber !")
    else:
        logger.error("[Test] ❌ Échec injection Jobber")
    return succes


def main():
    logger.info("=" * 60)
    logger.info("  TEST PIPELINE ALFRED (PC)")
    logger.info("  Pi SQLite → Enrichissement GPT → Jobber")
    logger.info("=" * 60)
    logger.info(f"Commande : {json.dumps(COMMANDE_PI, ensure_ascii=False)}")
    logger.info("=" * 60)

    # Vérifications préalables
    if not check_server():
        sys.exit(1)
    if not check_session():
        sys.exit(1)

    # Étape 1 : Enrichissement
    enrichie = enrichir(COMMANDE_PI)
    if enrichie is None:
        logger.error("[Test] Pipeline arrêté — enrichissement échoué")
        sys.exit(1)

    # Étape 2 : Injection Jobber
    succes = injecter_jobber(enrichie)

    logger.info("=" * 60)
    if succes:
        logger.success("✅  PIPELINE COMPLET — Données Pi → Jobber OK !")
    else:
        logger.error("❌  PIPELINE ÉCHOUÉ — Voir logs ci-dessus")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
