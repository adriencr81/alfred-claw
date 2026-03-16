"""
server/main.py
─────────────────────────────────────────────────────────────────────────────
Serveur central Alfred — tourne sur PC/cloud.
Expose les endpoints appelés par le Raspberry Pi :
  GET  /health      → ping pour vérifier la connectivité
  POST /enrichir    → enrichit une CommandeValidee via GPT (prix, référence, TVA)
  POST /planifier   → enregistre une intervention planning
─────────────────────────────────────────────────────────────────────────────
Lancement :
  pip install -r server/requirements.txt
  uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel, Field
from json_repair import repair_json

load_dotenv()

app = FastAPI(title="Alfred Central Server", version="1.0.0")
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")


# ─── Modèles ──────────────────────────────────────────────────────────────────

class CommandeValidee(BaseModel):
    client: str
    item: str
    quantite: float
    action: str
    notes: str = ""


class CommandeEnrichie(BaseModel):
    client: str
    item: str
    quantite: float
    action: str
    notes: str = ""
    prix_unitaire_ht: float = Field(default=0.0, ge=0)
    tva_pct: float = Field(default=20.0, ge=0)
    reference_produit: str = ""
    alerte: str = ""


class Intervention(BaseModel):
    client: str
    type_intervention: str
    date: str
    technicien: str = ""
    duree_heures: float = 4.0
    notes: str = ""


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Ping utilisé par le Raspberry Pi pour vérifier la connexion."""
    return {"status": "ok"}


@app.post("/enrichir", response_model=CommandeEnrichie)
def enrichir(commande: CommandeValidee) -> CommandeEnrichie:
    """
    Enrichit une commande via GPT :
    - Ajoute le prix unitaire HT estimé
    - Ajoute la référence produit
    - Vérifie la cohérence des données
    - Remonte une alerte si quelque chose est suspect
    """
    logger.info(f"[Enrichir] Traitement : {commande.client} — {commande.item} x{commande.quantite}")

    prompt = f"""
Tu es l'agent administratif d'une entreprise d'installation solaire et d'artisanat.
Tu reçois une commande brute saisie vocalement sur chantier. Enrichis-la.

Commande reçue :
{json.dumps(commande.model_dump(), ensure_ascii=False, indent=2)}

Ta mission :
1. Estime un prix unitaire HT réaliste pour l'item (en euros, marché français).
2. Propose une référence produit courte (ex: "PAN-MONO-400W", "MO-ELEC-H", "BAT-LI-100AH").
3. Vérifie que la quantité est cohérente avec l'item (ex: 1000 panneaux = suspect).
4. Si quelque chose est anormal, remplis le champ "alerte" avec une phrase courte.

Réponds UNIQUEMENT avec du JSON pur, sans texte autour :
{{
  "client": "...",
  "item": "...",
  "quantite": 0,
  "action": "...",
  "notes": "...",
  "prix_unitaire_ht": 0.0,
  "tva_pct": 20.0,
  "reference_produit": "...",
  "alerte": ""
}}
"""

    try:
        response = client_openai.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        raw = response.choices[0].message.content or ""
        logger.debug(f"[Enrichir] Réponse GPT brute : {raw}")

        repaired = repair_json(raw)
        data = json.loads(repaired)
        enrichie = CommandeEnrichie(**data)

        if enrichie.alerte:
            logger.warning(f"[Enrichir] ⚠️ Alerte : {enrichie.alerte}")

        logger.success(f"[Enrichir] ✅ {commande.client} — {enrichie.reference_produit} @ {enrichie.prix_unitaire_ht}€ HT")
        return enrichie

    except Exception as e:
        logger.error(f"[Enrichir] Erreur GPT : {e}")
        # Fallback : retourne la commande non enrichie plutôt que de planter
        return CommandeEnrichie(**commande.model_dump())


@app.post("/planifier")
def planifier(intervention: Intervention) -> dict:
    """
    Enregistre une intervention planning.
    Pour le POC : log + retour OK.
    À brancher sur Google Calendar / outil planning en prod.
    """
    logger.info(
        f"[Planifier] {intervention.client} — {intervention.type_intervention} "
        f"le {intervention.date} ({intervention.duree_heures}h)"
    )
    # TODO: intégrer Google Calendar API ou outil planning interne
    return {"status": "planifie", "intervention": intervention.model_dump()}
