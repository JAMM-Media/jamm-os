# app/services/totp_service.py

import base64
import io
import json
import random
import string

import bcrypt as _bcrypt_lib
import pyotp
import qrcode


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "JAMM PX") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_code_base64(uri: str) -> str:
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes() -> tuple[list[str], list[str]]:
    """
    Generates 10 random 10-character backup codes.
    Returns (raw_codes, hashed_codes).
    Raw codes are shown to the user once and never stored.
    """
    chars = string.ascii_uppercase + string.digits
    raw_codes = ["".join(random.choices(chars, k=10)) for _ in range(10)]
    hashed_codes = [
        _bcrypt_lib.hashpw(code.encode(), _bcrypt_lib.gensalt()).decode()
        for code in raw_codes
    ]
    return raw_codes, hashed_codes


def verify_backup_code(stored_hashes_json: str, code: str) -> tuple[bool, str]:
    """
    Checks code against all stored hashes. Single-use: removes the matched
    hash from the list on success.
    Returns (matched, updated_json).
    """
    hashes: list[str] = json.loads(stored_hashes_json)
    for i, h in enumerate(hashes):
        if _bcrypt_lib.checkpw(code.encode(), h.encode()):
            hashes.pop(i)
            return True, json.dumps(hashes)
    return False, stored_hashes_json
