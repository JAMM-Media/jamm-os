# app/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token

router = APIRouter()


@router.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Issues a JWT on successful login.

    The token now includes:
    - "sub": user's UUID
    - "firm_id": the firm this user belongs to
    - "token_version": current version (for session invalidation)

    Why include firm_id in the token?
    Every subsequent API request needs to know which firm's data to query.
    Embedding it in the token means no extra DB lookup per request.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    access_token = create_access_token(data={
        "sub": str(user.id),
        "firm_id": str(user.firm_id),
        "token_version": user.token_version,
    })

    return {"access_token": access_token, "token_type": "bearer"}