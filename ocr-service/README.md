# PokeCollect OCR Service

Servizio OCR per scansionare carte Pokémon TCG con intelligenza artificiale e **validazione rigorosa al 100%**.

## 🎯 Caratteristiche Principali

- **1 Risultato, Massima Precisione**: Niente più risultati multipli ambigui - solo la carta corretta o nessuna
- **Validazione Rigorosa**: 4 livelli di controllo per garantire match affidabili
- **Fuzzy Matching Intelligente**: Gestisce typo e varianti nei nomi
- **Batch Upload**: Scansiona più carte contemporaneamente
- **Webapp Integrata**: Interfaccia drag & drop moderna

## 🔒 Sistema di Validazione Strict

Il sistema applica **4 regole rigorose** prima di accettare un match:

### Regola 1: Score Minimo 70/100
La carta deve ottenere almeno **70 punti** su 100 nel sistema di scoring:
- Nome carta: 40 punti max
- Numero carta: 30 punti max
- Nome set: 15 punti max
- Codice set: 10 punti max
- Rarità: 5 punti max

### Regola 2: Numero Carta Perfetto
Se l'OCR rileva un numero carta, **DEVE** coincidere esattamente:
```
OCR: "025"  →  Carta: "025"  ✅ ACCEPT
OCR: "025"  →  Carta: "25"   ❌ REJECT
```

### Regola 3: Similarità Nome ≥85%
Il nome della carta deve avere almeno **85% di similarità** con quello estratto:
```
OCR: "Pikachu"     →  Carta: "Pikachu"      ✅ 100% similarity
OCR: "Pikachuu"    →  Carta: "Pikachu"      ✅ 95% similarity
OCR: "Raichu"      →  Carta: "Pikachu"      ❌ 65% similarity - REJECT
```

### Regola 4: Nessuna Ambiguità
Se il **2° miglior candidato** ha uno score troppo vicino (gap <15 punti), **il match viene rifiutato**:
```
Candidato 1: 85 punti
Candidato 2: 84 punti  →  Gap = 1  ❌ REJECT (ambiguo)

Candidato 1: 92 punti
Candidato 2: 65 punti  →  Gap = 27  ✅ ACCEPT (chiaro)
```

## 🌐 Webapp

Apri il browser su `http://localhost:8000` per accedere all'interfaccia web.

**Nuove Funzionalità UI:**
- **Badge "✓ VERIFICATO"** per match ≥80%
- **Badge "⚠ DA VERIFICARE"** per match 70-79%
- **Bordo verde** per match affidabili
- **Bordo arancione** per match da verificare manualmente
- **Messaggio debug dettagliato** se nessun match trovato

## 🛠️ Installazione Locale

```bash
# Crea ambiente virtuale
python3 -m venv .venv
source .venv/bin/activate  # Su Windows: .venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Configura variabili ambiente
cp .env.example .env
# Modifica .env con le tue chiavi API

# Avvia server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 API Endpoints

### `GET /`
Webapp HTML per scansione interattiva

### `POST /scan`
Scansiona una singola carta con validazione rigorosa

**Request:**
- Content-Type: `multipart/form-data`
- Campo: `file` (immagine)

**Response (Successo):**
```json
{
  "candidates": [
    {
      "card_id": "sv1-025",
      "name": "Pikachu",
      "confidence": 92,
      "price_eur": 2.50,
      "image_url": "https://...",
      "set_name": "Scarlet & Violet",
      "card_number": "025",
      "rarity": "Common"
    }
  ],
  "raw": {
    "name": "Pikachu",
    "card_number": "025",
    "set_name": "Scarlet & Violet",
    "set_code": "sv1",
    "rarity": "Common",
    "language": "en"
  }
}
```

**Response (Nessun Match):**
```json
{
  "candidates": [],
  "raw": { ... },
  "error": "not_found",
  "debug": "📋 Dati estratti dall'OCR:\n  • Nome: 'Pikachu'\n  • Numero: '025'\n  ...\n\n❌ Nessun match con confidence ≥70% trovato."
}
```

### `POST /add-to-collection`
Aggiunge carta alla collezione Supabase dell'utente

**Headers:**
- `Authorization: Bearer <supabase-user-token>`

**Body:**
```json
{
  "card_id": "sv1-025"
}
```

## 🔑 Variabili Ambiente

| Variabile | Richiesto | Descrizione |
|-----------|-----------|-------------|
| `OPENAI_API_KEY` | ✅ Sì | API key OpenAI per GPT-4o Vision |
| `TCG_API_KEY` | ❌ No | Pokemon TCG API key (aumenta rate limit) |
| `SUPABASE_URL` | ❌ No | URL progetto Supabase |
| `SUPABASE_ANON_KEY` | ❌ No | Anon key Supabase |

## 🧪 Strategia di Matching

Il sistema prova **3 livelli progressivi** di matching:

### Livello 1: Match Completo
```
Query: name:"Pikachu" number:"025" set.name:"Scarlet & Violet"
Validazione: STRICT (4 regole)
```

### Livello 2: Senza Info Set
```
Query: name:"Pikachu" number:"025"
Validazione: STRICT (4 regole)
```

### Livello 3: Solo Numero
```
Query: number:"025"
Validazione: STRICT (4 regole)
```

**Se tutti e 3 i livelli falliscono → "Carta non trovata"**

## 📊 Confidence Score Spiegato

| Range | Significato | Badge | Azione Consigliata |
|-------|-------------|-------|-------------------|
| **80-100%** | Match quasi certo | ✓ VERIFICATO | Aggiungi con fiducia |
| **70-79%** | Match probabile | ⚠ DA VERIFICARE | Controlla manualmente |
| **<70%** | Match rifiutato | ❌ REJECTED | Non mostrato all'utente |

## 🐳 Docker

```bash
docker build -t pokecollect-ocr .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e TCG_API_KEY=your_key \
  pokecollect-ocr
```

## 🔧 Sviluppo

```bash
# Run con hot-reload
uvicorn main:app --reload

# Test fuzzy matching
python3 test_similarity.py

# Test endpoint
curl -X POST http://localhost:8000/scan \
  -F "file=@carta.jpg"
```

## 💡 Troubleshooting

### "Carta non trovata" anche con foto nitida

1. **Controlla il debug output** nel messaggio di errore:
   - Il nome è stato letto correttamente dall'OCR?
   - Il numero carta è corretto?

2. **Verifica che la carta esista nel database Pokemon TCG**:
   ```bash
   curl "https://api.pokemontcg.io/v2/cards?q=name:Pikachu"
   ```

3. **Prova con una foto migliore**:
   - Nome e numero ben visibili
   - Niente riflessi o ombre
   - Buona illuminazione
   - Testo non sfocato

### Match rifiutato con confidence 65-69%

Questo è normale! Il sistema **privilegia la precisione**:
- Meglio nessun risultato che un risultato sbagliato
- Prova a migliorare la qualità della foto
- Controlla che nome/numero siano leggibili

## 📈 Metriche Attese

| Metrica | Valore Target |
|---------|---------------|
| **Precision (match corretti)** | >95% |
| **False Positives** | <3% |
| **OCR Success Rate** | >90% |
| **Latency per scan** | 3-8 secondi |

---

**Motto del progetto:** 
> "Un solo risultato, ma quello giusto. Zero compromessi sulla precisione." 🎯
