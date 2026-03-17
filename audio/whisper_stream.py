"""
audio/whisper_stream.py
─────────────────────────────────────────────────────────────────────────────
Pipeline de capture audio et transcription via whisper.cpp.
- Écoute le micro jusqu'à détection de silence.
- Sauvegarde en WAV temporaire.
- Appelle whisper.cpp en subprocess pour transcription offline.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import signal
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
import pyaudio
from loguru import logger

# ─── Paramètres audio ─────────────────────────────────────────────────────────
SAMPLE_RATE = 44_100       # Hz — taux natif du micro USB (rééchantillonné à 16k pour Whisper)
WHISPER_RATE = 16_000      # Hz — requis par Whisper
CHANNELS = 1               # Mono
FORMAT = pyaudio.paInt16   # 16 bits
CHUNK = 1_024              # Taille du buffer par lecture
SILENCE_THRESHOLD = 800    # Amplitude RMS en-dessous = silence
SILENCE_DURATION = 1.5     # Secondes de silence pour arrêter l'enregistrement
MAX_DURATION = 10          # Secondes max d'enregistrement


class WhisperStream:
    """Capture audio + transcription locale via whisper.cpp."""

    def __init__(self, whisper_bin: str = "whisper-cpp", model_path: str = "models/ggml-small.bin"):
        self.whisper_bin = whisper_bin
        self.model_path = model_path

    # ── Capture audio avec détection de silence ───────────────────────────────
    def enregistrer(self) -> Path:
        """
        Enregistre le micro jusqu'à détection de silence.
        Retourne le chemin du fichier WAV temporaire.
        """
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        logger.info("[Whisper] 🎙️ Écoute en cours... (parlez maintenant)")
        frames: list[bytes] = []
        silent_chunks = 0
        max_silent_chunks = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK)
        max_chunks = int(MAX_DURATION * SAMPLE_RATE / CHUNK)

        def _alarm_handler(signum, frame):
            raise TimeoutError("Durée max atteinte")

        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(MAX_DURATION)

        try:
            for _ in range(max_chunks):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

                audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                rms = np.sqrt(np.mean(audio_array**2)) if len(audio_array) > 0 else 0

                if rms < SILENCE_THRESHOLD:
                    silent_chunks += 1
                    if silent_chunks >= max_silent_chunks and len(frames) > max_silent_chunks:
                        logger.info("[Whisper] ✅ Silence détecté — fin de l'enregistrement")
                        break
                else:
                    silent_chunks = 0
        except TimeoutError:
            logger.info("[Whisper] ⏱️ Durée max atteinte — fin de l'enregistrement")
        finally:
            signal.alarm(0)

        stream.stop_stream()
        stream.close()

        # Sauvegarde dans un fichier WAV temporaire (avant terminate)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        audio.terminate()

        # Rééchantillonnage 44100 → 16000 Hz via ffmpeg (requis par Whisper)
        wav_orig = Path(tmp.name)
        wav_16k = wav_orig.with_suffix(".16k.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_orig), "-ar", str(WHISPER_RATE), str(wav_16k)],
            capture_output=True,
        )
        wav_orig.unlink(missing_ok=True)

        logger.debug(f"[Whisper] Audio rééchantillonné : {wav_16k}")
        return wav_16k

    # ── Transcription via whisper.cpp ─────────────────────────────────────────
    def transcrire(self, wav_path: Path) -> str:
        """
        Appelle whisper.cpp en subprocess et retourne le texte transcrit.
        Nécessite que whisper.cpp soit compilé et disponible dans PATH.
        """
        logger.info(f"[Whisper] Transcription de {wav_path.name}...")

        cmd = [
            self.whisper_bin,
            "-m", self.model_path,
            "-f", str(wav_path),
            "-l", "en",        # Langue anglaise
            "--no-timestamps",
            "-otxt",           # Sortie texte brut
            "-of", str(wav_path.with_suffix("")),  # Fichier de sortie
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error(f"[Whisper] Erreur whisper.cpp : {result.stderr}")
                raise RuntimeError(f"whisper.cpp a échoué : {result.stderr}")

            txt_path = wav_path.with_suffix(".txt")
            texte = txt_path.read_text(encoding="utf-8").strip()
            logger.success(f"[Whisper] Transcription : '{texte}'")

            # Nettoyage des fichiers temporaires
            wav_path.unlink(missing_ok=True)
            txt_path.unlink(missing_ok=True)

            return texte

        except subprocess.TimeoutExpired:
            logger.error("[Whisper] Timeout — whisper.cpp trop lent")
            raise

    # ── Pipeline complet ──────────────────────────────────────────────────────
    def ecouter_et_transcrire(self) -> str:
        """Capture audio + transcription en une seule étape."""
        wav_path = self.enregistrer()
        return self.transcrire(wav_path)
