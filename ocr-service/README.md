# PokeCollect OCR Service

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=your_key
export TCG_API_KEY=your_key
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Endpoint

- `POST /scan` (multipart/form-data, file field `file`)

## Environment

- `TCG_API_KEY`
