# app/schemas/staff_refresh.py

from pydantic import BaseModel


class StaffRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
