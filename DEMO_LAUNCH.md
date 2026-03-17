# Alfred — Script de lancement démo

## Scénario
> "Alfred, create a quote — 3 solar panels for Johnson."
> → Quote **$750** créée dans Jobber en ~60 secondes.

---

## ÉTAPE 1 — PC : Préparer Chrome (1 fois par session)

```powershell
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=C:\Temp\chrome-debug
```

- Aller sur **app.getjobber.com** et se connecter si nécessaire
- Laisser Chrome ouvert (ne pas le fermer)

---

## ÉTAPE 2 — PC : Démarrer LM Studio

- Ouvrir **LM Studio**
- Charger `meta-llama-3.1-8b-instruct`
- Démarrer le serveur local → port **1234**

---

## ÉTAPE 3 — PC : Démarrer le serveur FastAPI

```powershell
cd C:\Users\gamer\alfred
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Vérifier : `http://localhost:8000/health` → `{"status":"ok"}`

---

## ÉTAPE 4 — Pi : Démarrer Alfred

```bash
ssh adrien@192.168.1.66
cd ~/alfred && source venv/bin/activate

# Pre-warm LLaMA (évite timeout au 1er appel — ~10s)
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2","prompt":"hi","stream":false}' > /dev/null &

python main.py
```

---

## ÉTAPE 5 — Enregistrer la commande

Sur le Pi, quand `>>> Appuyez sur Entrée pour parler...` apparaît :

1. Appuyer sur **Entrée**
2. Parler clairement : **"Alfred, create a quote — three solar panels for Johnson"**
3. Attendre ~10s (enregistrement automatique)

Logs attendus sur le Pi :
```
[Whisper] Transcription : Alfred, create a quote. Three solar panels for Johnson.
[LLaMA] JSON extrait : {"client":"Johnson","item":"Solar Panel","quantite":3,"action":"ajouter_devis"}
[DB] Commande #X sauvegardée
[Sync] Commande #X synchronisée ✅
```

---

## ÉTAPE 6 — Le PC traite et crée le devis

Logs attendus sur le PC (uvicorn) :
```
[Traiter] Commande reçue : Johnson — Solar Panel x3
[Enrichir] Solar Panel @ 250.0€ HT ✅
[JobberBot] CDP connecté ✅
[JobberBot] Client "Johnson" sélectionné ✅
[JobberBot] Solar Panel ajouté, qty=3, prix=250 ✅
[JobberBot] Quote créée ✅
```

→ **Quote $750 visible dans Jobber** 🎉

---

## Dépannage rapide

| Problème | Solution |
|---|---|
| Session Jobber expirée | `python tools/jobber_setup_session.py` |
| LLaMA timeout | Pre-warm avec curl avant de lancer main.py |
| Produit non trouvé | Vérifier que "Solar Panel" existe dans le catalogue Jobber |
| Pi ne sync pas | Vérifier `CENTRAL_SERVER_URL=http://192.168.1.25:8000` dans `.env` Pi |
| uvicorn prend pas les changements | Ctrl+C + relancer uvicorn |
| Chrome CDP non trouvé | Relancer Chrome avec `--remote-debugging-port=9222` |

---

## Test PC seul (sans Pi, pour vérifier le pipeline)

```powershell
cd C:\Users\gamer\alfred
python tools/test_pipeline.py
```

Simule la commande Johnson/Solar Panel/qty=3 directement depuis le PC.
