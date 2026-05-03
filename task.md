## Standing Rules — Always Follow

- SQLAlchemy 2.0 select() style only — no legacy query style
- firm_id always injected server-side from JWT — never from client
- Background tasks that touch the DB must create their own SessionLocal() in a try/finally block
- native_enum=True never used for enums with dots or special characters — store as VARCHAR
- extra_metadata is the SQLAlchemy attribute name (metadata is reserved)
- Login endpoint uses JSON body (LoginRequest), not OAuth2 form data
- Every file starts with a path comment
- Read models before writing tests — flag missing fields before making changes
- Run pytest after every significant change
- bcrypt is called directly — do not reintroduce passlib

## Current Task — CORS and TrustedHostMiddleware production config

### Context
Two placeholders in the codebase need to be updated so the app works
correctly in production. No migration needed. No tests needed.
This is a config-only change.

### Step 1 — Read these files first

Read in full:
- app/core/config.py
- app/main.py

### Step 2 — Update BACKEND_CORS_ORIGINS in app/core/config.py

Currently BACKEND_CORS_ORIGINS is hardcoded as a list:
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

Replace it with a field that reads from an environment variable but
falls back to the localhost values for local development:

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

This means if BACKEND_CORS_ORIGINS is set as a comma-separated string
in the environment variable (e.g.
BACKEND_CORS_ORIGINS=https://app.jammpx.com,https://jammpx.com)
it will be parsed correctly. If not set, it falls back to the localhost
defaults.

Confirm field_validator is already imported from pydantic. If not add it.

### Step 3 — Update TrustedHostMiddleware in app/main.py

Currently the allowed_hosts list contains a placeholder:
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "testserver",
        "*.yourdomain.com",
    ],

Replace it with a list that includes the real production domains:
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "testserver",
        "jammpx.com",
        "*.jammpx.com",
    ],

### Step 4 — Add FRONTEND_URL to config

Check if FRONTEND_URL in config.py is hardcoded to localhost.
If it is, confirm it already reads from environment variables via
the SettingsConfigDict env_file setup — it should automatically
pick up FRONTEND_URL from .env if set. Just confirm this is the
case and note it in the report. No change needed if it already
works this way.

### Step 5 — Run pytest

Run: python -m pytest tests/ --tb=no -q

Report summary line only. Confirm no new failures.

### Step 6 — Report back

Paste:
- The updated BACKEND_CORS_ORIGINS section in config.py
- The updated TrustedHostMiddleware section in main.py
- pytest summary line