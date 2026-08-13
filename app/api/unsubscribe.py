# app/api/unsubscribe.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.unsubscribe_service import verify_and_process_unsubscribe

router = APIRouter(prefix="/unsubscribe", tags=["Unsubscribe"])

# NOTE: No frontend confirmation page is built in this task -- this endpoint
# returns plain JSON. A real branded confirmation page (frontend/src/app/unsubscribe/)
# is future work. Flag for follow-up before production deploy.


@router.get("/{token}", status_code=200)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    """Public, unauthenticated unsubscribe endpoint.

    The token in the URL is the RAW token (not the hash). The service layer
    hashes it before any DB lookup, matching the magic-link precedent.
    """
    success = verify_and_process_unsubscribe(db=db, raw_token=token)
    if success:
        return {
            "status": "unsubscribed",
            "message": "You have been unsubscribed. You will not receive further marketing emails from this firm.",
        }
    return {
        "status": "invalid",
        "message": "This unsubscribe link is no longer valid or has already been used.",
    }
