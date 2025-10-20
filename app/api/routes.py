from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..db.session import get_db

router = APIRouter()

@router.get("/health", tags=["system"])
def health():
    return {"status": "ok"}

@router.get("/db-check", tags=["system"])
def db_check(db: Session = Depends(get_db)):
    """
    Runs a trivial SELECT 1 against your Postgres to prove the connection works.
    """
    result = db.execute(text("SELECT 1")).scalar_one()
    return {"db": "connected", "result": int(result)}

