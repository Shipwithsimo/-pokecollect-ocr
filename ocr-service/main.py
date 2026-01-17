import os
import re
from io import BytesIO
from typing import List, Optional

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract

TCG_API_KEY = os.environ.get("TCG_API_KEY")
TCG_BASE_URL = "https://api.pokemontcg.io/v2"

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


def extract_name(texts: List[str]) -> Optional[str]:
    candidates = []
    for text in texts:
        cleaned = re.sub(r"[^A-Za-z\s'\-]", " ", text).strip()
        if 3 <= len(cleaned) <= 32:
            candidates.append(cleaned)

    if not candidates:
        return None

    preferred = sorted(candidates, key=lambda value: (len(value), value))
    return preferred[-1]


def build_query(name: Optional[str], number: Optional[str]) -> Optional[str]:
    clauses = []

    if name:
        clauses.append(f'name:"{name}"')

    if number:
        clauses.append(f'number:"{number}"')

    return " ".join(clauses) if clauses else None


@app.post("/scan")
async def scan_card(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    image = Image.open(BytesIO(content)).convert("RGB")
    raw_text = pytesseract.image_to_string(image, lang="eng", config="--psm 6")
    results = [line.strip() for line in raw_text.splitlines() if line.strip()]
    texts = [text for text in results if text]

    name = extract_name(texts)
    number = extract_card_number(texts)
    query = build_query(name, number)

    if not query:
        raise HTTPException(status_code=422, detail="Unable to extract card info")

    card = fetch_card_by_query(query)

    if not card and name:
        card = fetch_card_by_query(f'name:"{name}"')

    if not card and number:
        card = fetch_card_by_query(f'number:"{number}"')

    if not card:
        return {
            "card_id": None,
            "name": name or "",
            "set_name": "",
            "set_code": "",
            "card_number": number or "",
            "rarity": "",
            "confidence": 30,
            "price_eur": None,
            "image_url": None,
            "raw": {
                "ocr_name": name,
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
            "ocr_name": name,
            "ocr_number": number,
            "query": query,
        },
    }
