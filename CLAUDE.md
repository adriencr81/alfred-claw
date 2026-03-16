# CLAUDE.md — Alfred (Claw)

## Contexte du projet
Alfred est le composant Edge (Raspberry Pi 5) du système **Claw** — un agent vocal offline-first pour artisans. Il transcrit des commandes vocales de chantier via Whisper.cpp, les valide localement avec LLaMA 3.2 (Ollama), et synchronise les données de facturation vers un orchestrateur cloud (GPT).

## Architecture
```
Voix → WhisperStream → OpenClawEngine (LLaMA) → LocalDB (SQLite) → SyncManager → FacturationAgent → Logiciel facturation
```

- **`core/openclaw_engine.py`** — Moteur d'orchestration principal, point central de la logique métier
- **`agents/facturation_agent.py`** — Enrichissement et injection vers le logiciel de facturation
- **`agents/planning_agent.py`** — Planification chantier
- **`tools/playwright_bot.py`** — Automation navigateur (CSS selectors à adapter par logiciel)
- **`tools/accounting_tools.py`** — Connecteurs API REST (Pennylane, Quickbooks, ERP)
- **`audio/whisper_stream.py`** — Capture micro + transcription Whisper.cpp
- **`brain/prompts.py`** — Tous les prompts LLM centralisés ici
- **`storage/local_db.py`** — SQLite offline-first
- **`sync/sync_server.py`** — Thread de synchro cloud en arrière-plan

## Stack technique
- Python 3.x, Raspberry Pi 5
- Whisper.cpp (transcription locale)
- Ollama + LLaMA 3.2 (validation métier locale)
- OpenAI GPT (orchestrateur cloud)
- Playwright (automation facturation)
- SQLite (stockage offline)
- loguru (logs)
- python-dotenv (config via `.env`)

## Variables d'environnement
Copier `.env.example` en `.env`. Les clés importantes :
- `OPENAI_API_KEY` — GPT cloud
- `OLLAMA_URL` / `OLLAMA_MODEL` — LLM local
- `WHISPER_MODEL` — taille du modèle (tiny/base/small/medium)
- `FACTURATION_TYPE` / `FACTURATION_URL` — logiciel cible
- `SYNC_INTERVAL` — fréquence synchro (secondes)

## Conventions
- Langue du code : français (variables, commentaires, logs)
- Tous les prompts LLM dans `brain/prompts.py`, jamais inline
- Le stockage SQLite est offline-first : écrire localement d'abord, synchro ensuite
- Pas de dépendance réseau dans le chemin critique (écoute → transcription → sauvegarde)
- Les sélecteurs CSS Playwright sont dans `tools/playwright_bot.py` et doivent rester configurables

## Lancement
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # remplir les valeurs
python main.py
```
