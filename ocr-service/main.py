import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps
from rapidfuzz import fuzz
from supabase import create_client, Client

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TCG_API_KEY = os.environ.get("TCG_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
TCG_BASE_URL = "https://api.pokemontcg.io/v2"

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize Supabase client
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    max_side = 1024
    width, height = image.size
    scale = max_side / max(width, height)
    if scale < 1:
        image = image.resize((int(width * scale), int(height * scale)))

    return image


def image_to_base64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def call_openai_vision(image_base64: str) -> Optional[Dict[str, str]]:
    if not OPENAI_API_KEY:
        return None

    prompt = (
        "Sei un esperto di carte Pokemon TCG. "
        "Dall'immagine, estrai i dati esatti della carta. "
        "Rispondi SOLO in JSON con chiavi: name, card_number, set_name, set_code, rarity, language. "
        "Se un campo non e' visibile, usa stringa vuota."
    )

    payload = {
        "model": "gpt-4o",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract structured data from Pokemon TCG cards."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            },
        ],
        "max_tokens": 400,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        error = response.text
        raise HTTPException(status_code=502, detail=f"OpenAI error: {error}")

    payload = response.json()
    content = payload.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None

    return {
        "name": (data.get("name") or "").strip(),
        "card_number": (data.get("card_number") or "").strip(),
        "set_name": (data.get("set_name") or "").strip(),
        "set_code": (data.get("set_code") or "").strip(),
        "rarity": (data.get("rarity") or "").strip(),
        "language": (data.get("language") or "").strip(),
    }


def fetch_cards_by_query(query: str, page_size: int = 20) -> List[Dict]:
    headers = {}
    if TCG_API_KEY:
        headers["X-Api-Key"] = TCG_API_KEY

    try:
        response = requests.get(
            f"{TCG_BASE_URL}/cards",
            params={"q": query, "pageSize": page_size},
            headers=headers,
            timeout=30,
        )
    except requests.Timeout:
        return []

    if response.status_code != 200:
        return []

    return response.json().get("data", [])


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    a_clean = a.lower().strip()
    b_clean = b.lower().strip()

    ratio = fuzz.ratio(a_clean, b_clean) / 100.0
    token_sort = fuzz.token_sort_ratio(a_clean, b_clean) / 100.0
    partial = fuzz.partial_ratio(a_clean, b_clean) / 100.0

    return (ratio * 0.5) + (token_sort * 0.3) + (partial * 0.2)


def score_card(card: Dict, extracted: Dict[str, str]) -> float:
    score = 0.0
    name = extracted.get("name")
    number = extracted.get("card_number")
    set_name = extracted.get("set_name")
    set_code = extracted.get("set_code")
    rarity = extracted.get("rarity")

    if name:
        score += similarity(name, card.get("name", "")) * 40
    if number:
        score += 30 if number.replace(" ", "") == card.get("number", "") else 0
    if set_name:
        score += similarity(set_name, card.get("set", {}).get("name", "")) * 15
    if set_code:
        score += similarity(set_code, card.get("set", {}).get("id", "")) * 10
    if rarity:
        score += similarity(rarity, card.get("rarity", "")) * 5

    return score


def build_queries(extracted: Dict[str, str]) -> List[str]:
    name = extracted.get("name")
    number = extracted.get("card_number")
    set_name = extracted.get("set_name")

    queries = []
    if name and number and set_name:
        queries.append(f'name:"{name}" number:"{number}" set.name:"{set_name}"')
    if name and number:
        queries.append(f'name:"{name}" number:"{number}"')
    if name and set_name:
        queries.append(f'name:"{name}" set.name:"{set_name}"')
    if name:
        queries.append(f'name:"{name}"')

    return queries


def to_candidate(card: Dict, confidence: float) -> Dict:
    return {
        "card_id": card.get("id"),
        "name": card.get("name"),
        "set_name": card.get("set", {}).get("name"),
        "set_code": card.get("set", {}).get("id"),
        "card_number": card.get("number"),
        "rarity": card.get("rarity"),
        "confidence": int(min(confidence, 100)),
        "price_eur": card.get("cardmarket", {}).get("prices", {}).get("averageSellPrice"),
        "image_url": (card.get("images") or {}).get("small"),
    }


def find_best_match(extracted: Dict[str, str], strict: bool = True) -> Optional[Dict]:
    """
    Trova LA carta migliore con altissima precisione.
    
    Args:
        extracted: Dati estratti dall'OCR
        strict: Se True, applica validazione rigorosa (solo match quasi perfetti)
    
    Returns:
        Una singola carta o None se nessun match affidabile
    """
    seen: Dict[str, float] = {}
    cards: Dict[str, Dict] = {}

    queries = build_queries(extracted)
    print(f"🔎 Query generate: {queries}")

    for query in queries:
        fetched = fetch_cards_by_query(query)
        print(f"📡 Query '{query}' → {len(fetched)} carte trovate")
        
        for card in fetched:
            card_id = card.get("id")
            if not card_id:
                continue
            score = score_card(card, extracted)
            
            # Debug per prime 5 carte
            if len(seen) < 5:
                print(f"  - {card.get('name')} #{card.get('number')} ({card.get('set', {}).get('name')}) → score: {score:.1f}")
            
            if card_id not in seen or score > seen[card_id]:
                seen[card_id] = score
                cards[card_id] = card

    if not seen:
        print("❌ Nessuna carta trovata nelle query")
        return None

    # Ordina per score
    ranked = sorted(seen.items(), key=lambda item: item[1], reverse=True)
    best_id, best_score = ranked[0]
    best_card = cards[best_id]
    
    print(f"🏆 Miglior candidato: {best_card.get('name')} #{best_card.get('number')} → score: {best_score:.1f}")
    
    if strict:
        # MODALITÀ STRICT: Validazione rigorosa
        
        # Regola 1: Score minimo 70 (almeno 70/100 punti)
        if best_score < 70:
            print(f"❌ REJECTED: Score troppo basso ({best_score:.1f} < 70)")
            return None
        
        # Regola 2: Se c'è numero carta nell'OCR, DEVE matchare perfettamente
        ocr_number = extracted.get("card_number", "").strip().replace(" ", "")
        card_number = best_card.get("number", "").strip()
        
        if ocr_number and ocr_number != card_number:
            print(f"❌ REJECTED: Numero carta non coincide (OCR: '{ocr_number}' vs Carta: '{card_number}')")
            return None
        
        # Regola 3: Nome deve avere almeno 85% di similarità
        ocr_name = extracted.get("name", "")
        card_name = best_card.get("name", "")
        name_similarity = similarity(ocr_name, card_name)
        
        if name_similarity < 0.85:
            print(f"❌ REJECTED: Nome troppo diverso ({name_similarity:.0%} < 85%)")
            return None
        
        # Regola 4: Se c'è un secondo candidato molto vicino, ambiguità!
        if len(ranked) > 1:
            second_score = ranked[1][1]
            gap = best_score - second_score
            
            if gap < 15:  # Differenza minima 15 punti
                print(f"⚠️ REJECTED: Troppa ambiguità (gap: {gap:.1f} < 15)")
                return None
        
        print(f"✅ ACCEPTED: Match affidabile al {best_score:.0f}%")
    
    return to_candidate(best_card, best_score)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/version")
async def version():
    """Endpoint per verificare la versione del codice"""
    return {
        "version": "2.0-strict",
        "mode": "single_result",
        "max_candidates": 1,
        "min_confidence": 70,
        "validation": "strict_4_rules"
    }


@app.post("/scan")
async def scan_card(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    image = Image.open(BytesIO(content))
    processed = preprocess_image(image)
    image_base64 = image_to_base64(processed)

    extracted = call_openai_vision(image_base64)
    if not extracted:
        return {
            "candidates": [],
            "raw": {},
            "error": "ocr_failed",
            "debug": "OpenAI Vision non ha restituito dati"
        }

    # Log per debug
    print(f"\n{'='*60}")
    print(f"🔍 OCR Estratto: {extracted}")
    print(f"{'='*60}\n")

    # Strategia 1: Match STRICT con tutti i dati
    print("🎯 Tentativo 1: Match strict completo...")
    best_match = find_best_match(extracted, strict=True)
    
    # Strategia 2: Se fallisce, riprova senza info sul set ma sempre strict
    if not best_match and extracted.get("name") and extracted.get("card_number"):
        print("\n🎯 Tentativo 2: Match strict senza info set...")
        best_match = find_best_match(
            {**extracted, "set_name": "", "set_code": ""}, 
            strict=True
        )
    
    # Strategia 3: Se il numero è molto affidabile, cerca solo per numero
    if not best_match and extracted.get("card_number") and len(extracted.get("card_number", "")) >= 2:
        print("\n🎯 Tentativo 3: Match strict solo numero carta...")
        best_match = find_best_match(
            {"name": "", "card_number": extracted.get("card_number"), "set_name": "", "set_code": "", "rarity": ""}, 
            strict=True
        )

    if not best_match:
        # Costruisci messaggio di debug dettagliato
        debug_msg = f"""
📋 Dati estratti dall'OCR:
  • Nome: '{extracted.get('name') or 'NON RILEVATO'}'
  • Numero: '{extracted.get('card_number') or 'NON RILEVATO'}'
  • Set: '{extracted.get('set_name') or 'NON RILEVATO'}'
  • Codice Set: '{extracted.get('set_code') or 'NON RILEVATO'}'
  • Rarità: '{extracted.get('rarity') or 'NON RILEVATO'}'

❌ Nessun match con confidence ≥70% trovato.

💡 Suggerimenti:
  1. Assicurati che nome e numero carta siano ben visibili
  2. Verifica che la carta esista nel database Pokemon TCG
  3. Prova con una foto più nitida e ben illuminata
  4. Controlla che il testo non sia riflesso o sfocato
        """.strip()
        
        print(f"\n❌ NESSUN MATCH AFFIDABILE TROVATO\n")
        
        return {
            "candidates": [],
            "raw": extracted,
            "error": "not_found",
            "debug": debug_msg
        }

    print(f"\n✅ CARTA IDENTIFICATA CON SUCCESSO!\n")
    
    # Restituisci array con 1 solo elemento per compatibilità
    return {
        "candidates": [best_match],
        "raw": extracted,
    }


@app.post("/add-to-collection")
async def add_to_collection(
    card_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Aggiunge una carta alla collezione dell'utente in Supabase.
    Richiede Authorization header con Bearer token di Supabase.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Fetch card details from Pokemon TCG API
        headers = {}
        if TCG_API_KEY:
            headers["X-Api-Key"] = TCG_API_KEY
        
        response = requests.get(
            f"{TCG_BASE_URL}/cards/{card_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Card not found in TCG API")
        
        card_data = response.json().get("data", {})
        
        # Create authenticated Supabase client with user token
        user_supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        user_supabase.auth.set_session(token, "")
        
        # Check if card already exists in user's collection
        existing = user_supabase.table("user_cards").select("*").eq("card_id", card_id).execute()
        
        if existing.data and len(existing.data) > 0:
            # Card exists - increment quantity
            current_quantity = existing.data[0].get("quantity", 1)
            result = user_supabase.table("user_cards").update({
                "quantity": current_quantity + 1
            }).eq("id", existing.data[0]["id"]).execute()
            
            return {
                "success": True,
                "action": "updated",
                "quantity": current_quantity + 1,
                "message": f"Quantità aggiornata a {current_quantity + 1}"
            }
        else:
            # New card - insert
            result = user_supabase.table("user_cards").insert({
                "card_id": card_id,
                "quantity": 1,
                "name": card_data.get("name"),
                "set_name": card_data.get("set", {}).get("name"),
                "image_url": card_data.get("images", {}).get("small"),
                "price_eur": card_data.get("cardmarket", {}).get("prices", {}).get("averageSellPrice")
            }).execute()
            
            return {
                "success": True,
                "action": "created",
                "quantity": 1,
                "message": "Carta aggiunta alla collezione"
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
