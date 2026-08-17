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

# then edit .env to set your DATABASE_URL
#
# Keep the postgresql+psycopg:// prefix. A plain postgresql:// URL silently
# selects psycopg2 instead of psycopg 3, and psycopg2 exceptions carry .pgcode
# where psycopg 3 carries .sqlstate, so every sqlstate error-code guard in the
# codebase stops firing with no error and no warning.
# tests/test_database_url_prefix.py guards this.

# Run
uvicorn app.main:app --reload

# Open http://127.0.0.1:8000/api/health
```

## Testing
```bash
pytest -q
```
