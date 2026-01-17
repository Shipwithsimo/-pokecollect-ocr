# PokeCollect OCR Service

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Tesseract must be available in the system path. On macOS:

```bash
brew install tesseract
```

## Endpoint

- `POST /scan` (multipart/form-data, file field `file`)

## Environment

- `TCG_API_KEY`
