import os
import re
import difflib
from io import BytesIO
from typing import List, Optional, Tuple

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
import pytesseract

TCG_API_KEY = os.environ.get("TCG_API_KEY")
TCG_BASE_URL = "https://api.pokemontcg.io/v2"
TCG_CARD_NAMES_URL = f"{TCG_BASE_URL}/cards?q=name:%20*&select=name&pageSize=250"

_cached_names: List[str] = []

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



def fetch_card_by_query(query: str):
    headers = {}
    if TCG_API_KEY:
        headers["X-Api-Key"] = TCG_API_KEY

    try:
        response = requests.get(
            f"{TCG_BASE_URL}/cards",
            params={"q": query, "pageSize": 1},
            headers=headers,
            timeout=45,
        )
    except requests.Timeout:
        return None

    if response.status_code != 200:
        return None

    data = response.json().get("data", [])
    return data[0] if data else None


def extract_card_number(texts: List[str]) -> Optional[str]:
    for text in texts:
        match = re.search(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b", text)
        if match:
            return match.group(0).replace(" ", "")
    return None


def fetch_card_names() -> List[str]:
    global _cached_names

    if _cached_names:
        return _cached_names

    headers = {}
    if TCG_API_KEY:
        headers["X-Api-Key"] = TCG_API_KEY

    names = set()
    page = 1

    while page <= 2:
        response = requests.get(
            TCG_CARD_NAMES_URL,
            params={"page": page},
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            break

        data = response.json().get("data", [])
        if not data:
            break

        for item in data:
            name = item.get("name")
            if name:
                names.add(name)

        page += 1

    _cached_names = sorted(names)
    return _cached_names


def match_name(candidate: str, names: List[str]) -> Optional[str]:
    if not candidate:
        return None

    matches = difflib.get_close_matches(candidate, names, n=1, cutoff=0.72)
    return matches[0] if matches else None


def extract_name(texts: List[str], names: List[str]) -> Tuple[Optional[str], Optional[str]]:
    candidates = []
    for text in texts:
        cleaned = re.sub(r"[^A-Za-z\s'\-]", " ", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if 3 <= len(cleaned) <= 32:
            candidates.append(cleaned)

    if not candidates:
        return None, None

    preferred = sorted(candidates, key=lambda value: (len(value), value))
    best_raw = preferred[-1]
    matched = match_name(best_raw, names)
    return matched, best_raw


def build_query(name: Optional[str], number: Optional[str]) -> Optional[str]:
    clauses = []

    if name:
        clauses.append(f'name:"{name}"')

    if number:
        clauses.append(f'number:"{number}"')

    return " ".join(clauses) if clauses else None


def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.resize((image.width * 2, image.height * 2))
    threshold = 160
    image = image.point(lambda value: 255 if value > threshold else 0)
    return image


@app.post("/scan")
async def scan_card(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    image = Image.open(BytesIO(content)).convert("RGB")
    processed = preprocess_image(image)
    raw_text = pytesseract.image_to_string(processed, lang="eng", config="--psm 6")
    results = [line.strip() for line in raw_text.splitlines() if line.strip()]
    texts = [text for text in results if text]

    names = fetch_card_names()
    name, raw_name = extract_name(texts, names)
    number = extract_card_number(texts)
    query = build_query(name, number)

    if not query:
        return {
            "card_id": None,
            "name": raw_name or "",
            "set_name": "",
            "set_code": "",
            "card_number": number or "",
            "rarity": "",
            "confidence": 30,
            "price_eur": None,
            "image_url": None,
            "raw": {
                "ocr_name": raw_name,
                "ocr_number": number,
                "query": "",
            },
            "error": "not_found",
        }

    card = fetch_card_by_query(query)

    if not card and name:
        card = fetch_card_by_query(f'name:"{name}"')

    if not card and number:
        card = fetch_card_by_query(f'number:"{number}"')

    if not card:
        return {
            "card_id": None,
            "name": name or raw_name or "",
            "set_name": "",
            "set_code": "",
            "card_number": number or "",
            "rarity": "",
            "confidence": 30,
            "price_eur": None,
            "image_url": None,
            "raw": {
                "ocr_name": raw_name,
                "ocr_number": number,
                "query": query,
            },
            "error": "not_found",
        }

    return {
        "card_id": card.get("id"),
        "name": card.get("name"),
        "set_name": card.get("set", {}).get("name"),
        "set_code": card.get("set", {}).get("id"),
        "card_number": card.get("number"),
        "rarity": card.get("rarity"),
        "confidence": 90,
        "price_eur": card.get("cardmarket", {}).get("prices", {}).get("averageSellPrice"),
        "image_url": (card.get("images") or {}).get("small"),
        "raw": {
            "ocr_name": raw_name,
            "ocr_number": number,
            "query": query,
        },
    }
