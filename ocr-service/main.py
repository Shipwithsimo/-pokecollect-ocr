import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TCG_API_KEY = os.environ.get("TCG_API_KEY")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
TCG_BASE_URL = "https://api.pokemontcg.io/v2"

app = FastAPI()

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

    width, height = image.size
    crop_ratio = 0.8
    crop_width = int(width * crop_ratio)
    crop_height = int(height * crop_ratio)
    left = max((width - crop_width) // 2, 0)
    top = max((height - crop_height) // 2, 0)
    right = left + crop_width
    bottom = top + crop_height
    return image.crop((left, top, right, bottom))


def image_to_base64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def call_openai_vision(image_base64: str) -> Optional[Dict[str, str]]:
    if not OPENAI_API_KEY:
        return None

    prompt = (
        "Estrai i dati della carta Pokemon dall'immagine. "
        "Rispondi SOLO in JSON con chiavi: name, card_number, set_name, set_code, rarity, language. "
        "Se un campo non e' visibile, usa stringa vuota."
    )

    payload = {
        "model": "gpt-4o",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract structured data from trading cards."},
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
        return None

    content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
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

    response = requests.get(
        f"{TCG_BASE_URL}/cards",
        params={"q": query, "pageSize": page_size},
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        return []

    return response.json().get("data", [])


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a.lower() == b.lower() else 0.5 if a.lower() in b.lower() else 0.0


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


def find_candidates(extracted: Dict[str, str]) -> List[Dict]:
    seen: Dict[str, float] = {}
    cards: Dict[str, Dict] = {}

    for query in build_queries(extracted):
        for card in fetch_cards_by_query(query):
            card_id = card.get("id")
            if not card_id:
                continue
            score = score_card(card, extracted)
            if card_id not in seen or score > seen[card_id]:
                seen[card_id] = score
                cards[card_id] = card

    ranked = sorted(seen.items(), key=lambda item: item[1], reverse=True)
    top = ranked[:3]
    return [to_candidate(cards[card_id], score) for card_id, score in top]


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
        }

    candidates = find_candidates(extracted)

    return {
        "candidates": candidates,
        "raw": extracted,
    }
