# Alfred — AI Coworker for the Physical World

> **Voice -> Local AI -> Any web app. No cloud. No API key. Raspberry Pi 5.**

**[▶ Watch the demo (64s)](https://www.youtube.com/watch?v=N6O4lkWjgTE)**

---

## English

### What is Alfred?

Alfred is a fully local AI agent that runs on a Raspberry Pi 5. You speak a command — it transcribes with Whisper.cpp, validates with LLaMA 3.2 via Ollama, and automatically fills in your business software (invoicing, job management) using Playwright.

No cloud. No subscription. No internet required on the job site.

**Demo scenario (validated POC):**
```
"Alfred, add a quote — 3 solar panels for Dupont."
-> Jobber opens, client selected, line items filled: 3 x 250 EUR = 750.00 EUR
-> Total time: ~12 seconds. Zero keyboard interaction.
```

---

### Why this matters

Field workers (electricians, plumbers, solar installers) lose 2+ hours per day on paperwork. Every existing solution requires a phone, a screen, or internet. Alfred requires none of these.

The deeper story: proof that a **$80 computer running open-source models can act as a fully autonomous agent** — understanding natural language, making decisions, and controlling web software without any API access.

---

### Technical stack

| Layer | Technology |
|---|---|
| Voice capture | Python `sounddevice` + VAD |
| Transcription | Whisper.cpp (local, ~1.2s) |
| Intent parsing | LLaMA 3.2 via Ollama (~0.8s) |
| Business logic | FastAPI orchestrator |
| Software automation | Playwright via Chrome CDP |
| Storage | SQLite (offline-first) |
| Hardware | Raspberry Pi 5 (8GB) |

**Non-obvious technical decisions:**

- **Chrome CDP over headless Chromium** — Jobber uses Cloudflare bot detection. Attaching to a real Chrome instance via `--remote-debugging-port=9222` bypasses it completely.
- **React Aria input trick** — Jobber line items use React Aria, which ignores `keyboard.type()`. We use `Input.insertText` via CDP DevTools protocol to trigger React synthetic events correctly.
- **Mouse coordinates over CSS selectors** — Jobber's client dropdown is dynamically positioned; real mouse clicks via CDP are more reliable than CSS selector clicks.

---

### Architecture

```
Raspberry Pi 5                    PC / Server
-----------------                 ----------------------------
Mic -> Whisper.cpp                FastAPI (/enrichir)
    -> LLaMA 3.2 (Ollama)    ->       -> LLM (LM Studio / GPT)
    -> SQLite (offline)           -> PlaywrightBot (CDP)
    -> SyncManager         ->         -> Jobber / Pennylane / QuickBooks
```

- Pi handles all real-time voice processing — works without internet
- PC/server handles software automation and LLM enrichment
- SQLite buffers everything locally; sync happens in background

---

### Current status (POC)

- [x] Voice capture + Whisper transcription on Pi
- [x] LLaMA 3.2 intent parsing (Ollama)
- [x] FastAPI orchestrator
- [x] Playwright -> Jobber (client selection + line items + totals)
- [x] CDP Chrome bypass (Cloudflare)
- [x] SQLite offline storage
- [ ] Pi -> PC end-to-end voice-to-invoice (in progress)
- [ ] Multi-agent: calls, photo posting, scheduling (roadmap)

---

### Run it yourself

**Prerequisites:**
- Raspberry Pi 5 (or any Linux machine with a mic)
- Ollama with `llama3.2` pulled
- Whisper.cpp compiled with `small` model
- Chrome with remote debugging enabled (PC side)
- A Jobber account (or adapt selectors for your software)

```bash
git clone https://github.com/adriencr81/alfred-claw
cd alfred-claw
pip install -r requirements.txt
playwright install chromium
cp .env.example .env

# Start Chrome with CDP (PC)
chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\Temp\chrome-debug

# Start FastAPI server (PC)
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# Start Alfred (Pi)
python main.py
```

---

### Adapting to your software

Alfred is not Jobber-specific. Open `tools/playwright_bot.py` and replace the CSS selectors for your invoicing software. Should work with Pennylane, QuickBooks, or any web-based tool.

---

### Vision

- **Today:** voice -> invoice (POC)
- **Next:** answer calls, post job site photos, manage scheduling
- **Goal:** a fully autonomous AI coworker for field workers — 100% local, costs less than a monthly SaaS subscription

---

### Contact

- Site: [getalfred-claw.tech](https://getalfred-claw.tech)
- Built by [@adriencr81](https://github.com/adriencr81)
- Alpha waitlist open

---

---

## Francais

### C'est quoi Alfred ?

Alfred est un agent IA 100% local sur Raspberry Pi 5. Tu parles — il transcrit avec Whisper.cpp, comprend avec LLaMA 3.2 via Ollama, et remplit automatiquement ton logiciel metier via Playwright.

Zero cloud. Zero abonnement. Zero connexion internet sur le chantier.

**Scenario demo (POC valide) :**
```
"Alfred, ajoute un devis — 3 panneaux solaires pour Dupont."
-> Jobber s'ouvre, client selectionne, lignes remplies : 3 x 250 EUR = 750.00 EUR
-> Temps total : ~12 secondes. Zero clavier.
```

---

### Pourquoi ca compte

Les artisans perdent 2h+ par jour en paperasse. Toutes les solutions existantes necessitent un telephone, un ecran, ou internet. Alfred n'en a besoin d'aucun.

Preuve qu'un **ordinateur a 80 EUR sur modeles open-source peut agir comme agent autonome** — comprendre le langage naturel et piloter des logiciels web sans API.

---

### Stack technique

| Couche | Technologie |
|---|---|
| Capture vocale | Python `sounddevice` + VAD |
| Transcription | Whisper.cpp (~1.2s) |
| Parsing intention | LLaMA 3.2 via Ollama (~0.8s) |
| Logique metier | Orchestrateur FastAPI |
| Automation | Playwright via Chrome CDP |
| Stockage | SQLite offline-first |
| Hardware | Raspberry Pi 5 (8GB) |

**Decisions techniques cles :**
- **Chrome CDP** — bypass Cloudflare (bloque Chromium headless)
- **React Aria trick** — `Input.insertText` via CDP pour declencher les evenements React
- **Clics souris** — plus fiables que les selecteurs CSS sur les dropdowns dynamiques

---

### Etat actuel (POC)

- [x] Whisper sur Pi
- [x] LLaMA 3.2 (Ollama)
- [x] FastAPI orchestrateur
- [x] Playwright -> Jobber (client + lignes + totaux)
- [x] Bypass Cloudflare CDP
- [x] SQLite offline
- [ ] End-to-end voix -> facture Pi -> PC (en cours)
- [ ] Multi-agent : appels, photos, planning (roadmap)

---

### Vision

- **Aujourd'hui :** voix -> devis
- **Ensuite :** appels, photos chantier, planning
- **Objectif :** coworker IA autonome pour artisans, 100% local

---

### Contact

- [getalfred-claw.tech](https://getalfred-claw.tech) — waitlist ouverte
