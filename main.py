"""
main.py — Point d'entrée Alfred sur Raspberry Pi
Boucle principale : écoute → transcription → extraction → validation → sync
"""
import os
import sys
import threading
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ── Configuration des logs ─────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL", "INFO"))
logger.add("storage/alfred.log", rotation="10 MB", retention="30 days", level="DEBUG")

from audio.whisper_stream import WhisperStream
from core.openclaw_engine import OpenClawEngine
from agents.facturation_agent import FacturationAgent
from storage.local_db import LocalDB
from sync.sync_server import SyncManager

def main():
    db = LocalDB()
    engine = OpenClawEngine(
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        db=db,
    )
    agent = FacturationAgent(db=db)
    whisper = WhisperStream(
        whisper_bin=os.getenv("WHISPER_BIN", "/home/adrien/whisper.cpp/build/bin/whisper-cli"),
        model_path=f"models/ggml-{os.getenv('WHISPER_MODEL','small')}.bin",
    )

    # Lancer la synchro en arrière-plan
    sync = SyncManager(db=db, agent=agent)
    sync.demarrer_en_thread()

    logger.info("🤖 Alfred prêt. Appuyez sur Entrée pour démarrer l'écoute (Ctrl+C pour quitter)")

    try:
        while True:
            input(">>> Appuyez sur Entrée pour parler...")
            texte = whisper.ecouter_et_transcrire()
            if texte.strip():
                try:
                    resultat = engine.traiter(texte)
                    type_action = resultat.get("type")
                    message = resultat.get("message", "")
                    if type_action == "chrono":
                        logger.info(f"[Chrono] {message}")
                    elif type_action == "bilan":
                        logger.info(f"\n{'─'*60}\n{message}\n{'─'*60}")
                    else:
                        logger.info(f"Commande #{resultat.get('cmd_id')} sauvegardée : {resultat.get('commande')}")
                except Exception as e:
                    logger.warning(f"Commande ignorée ({e}) — réessayez")
    except KeyboardInterrupt:
        logger.info("Alfred arrêté.")
        sync.arreter()

if __name__ == "__main__":
    main()