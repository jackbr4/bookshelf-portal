from datetime import datetime, timedelta, timezone
from typing import Tuple
import secrets

from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from .settings import settings

_serializer = URLSafeTimedSerializer(settings.app_session_secret)


def create_session_token() -> Tuple[str, datetime]:
    payload = {"v": secrets.token_hex(16)}
    token = _serializer.dumps(payload)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
    return token, expires_at


def verify_session_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=int(settings.session_ttl_hours * 3600))
        return True
    except (BadSignature, SignatureExpired):
        return False


async def get_session(request: Request):
    token = request.cookies.get("session_token")
    if not token or not verify_session_token(token):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return True
