# app/schemas/portal.py

import uuid
from datetime import datetime

from pydantic import BaseModel


class MagicLinkRequest(BaseModel):
    client_id: uuid.UUID
    expiry_hours: int = 48


class MagicLinkResponse(BaseModel):
    sent: bool
    expires_at: datetime


class MagicLinkAuthRequest(BaseModel):
    # Not used as a body schema — token comes from query param
    pass


class ClientMagicLinkRequest(BaseModel):
    email: str
