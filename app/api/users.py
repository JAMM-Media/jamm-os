# app/api/users.py
from fastapi import APIRouter, Depends
from app.core.security import oauth2_scheme
from jose import JWTError, jwt
from app.core.config import get_settings
from fastapi import HTTPException, status

router = APIRouter()
settings = get_settings()

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return {"user_id": user_id}

@router.get("/users/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
