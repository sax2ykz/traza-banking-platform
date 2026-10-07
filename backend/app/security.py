"""Local synthetic user authentication. Not a certified banking identity service.
Credentials must NOT be supplied through chat, committed to source or logged.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.security_models import AppUser
from app.session import get_db

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
JWT_ISSUER = 'bancocloud-local'
JWT_AUDIENCE = 'bancocloud-api'
JWT_TTL_MIN = 30
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=2)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')


def jwt_secret() -> str:
    value = os.getenv('BC_JWT_SECRET', '')
    if len(value) < 48:
        raise RuntimeError('BC_JWT_SECRET is missing/too short: generate it locally in .env')
    return value


def valid_password(value: str) -> bool:
    return bool(12 <= len(value) <= 128 and re.search(r'[A-Z]', value) and
                re.search(r'[a-z]', value) and re.search(r'[0-9]', value) and
                re.search(r'[^A-Za-z0-9]', value))


def hash_password(value: str) -> str:
    if not valid_password(value):
        raise ValueError('Password must have 12-128 characters including upper/lower/digit/symbol')
    return _hasher.hash(value)


def verify_password(value: str, encoded: str) -> bool:
    try:
        return _hasher.verify(encoded, value)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_token(user: AppUser) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        'sub': str(user.id), 'iss': JWT_ISSUER, 'aud': JWT_AUDIENCE,
        'iat': now, 'nbf': now, 'exp': now + timedelta(minutes=JWT_TTL_MIN),
    }
    return jwt.encode(claims, jwt_secret(), algorithm='HS256')


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> AppUser:
    unauth = HTTPException(401, 'Unauthorized', headers={'WWW-Authenticate': 'Bearer'})
    try:
        claims = jwt.decode(token, jwt_secret(), algorithms=['HS256'],
                            issuer=JWT_ISSUER, audience=JWT_AUDIENCE,
                            options={'require': ['sub', 'exp', 'iss', 'aud', 'iat']})
        user_id = UUID(claims['sub'])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauth
    user = db.get(AppUser, user_id)
    if user is None or not user.active:
        raise unauth
    return user


def require_admin(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role != 'ADMIN':
        raise HTTPException(403, 'Administrator role required')
    return user


def verify_customer_access(user: AppUser, customer_id: UUID, *, allow_admin: bool = True) -> None:
    if allow_admin and user.role == 'ADMIN':
        return
    if user.role != 'CUSTOMER' or user.customer_id != customer_id:
        raise HTTPException(403, 'Access denied for this customer')
