# JAMM OS Backend Starter

## Quickstart

```bash
# from the backend folder
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Copy env
# Windows (PowerShell):
#   copy .env.example .env
# macOS/Linux:
#   cp .env.example .env

# then edit .env to set your DATABASE_URL if needed

# Run
uvicorn app.main:app --reload

# Open http://127.0.0.1:8000/api/health
```

## Testing
```bash
pytest -q
```
