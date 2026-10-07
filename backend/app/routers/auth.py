"""Synthetic self-registration and JWT login for LOCAL BancoCloud development."""
from secrets import token_hex
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, Customer
from app.security import create_token, current_user, hash_password, valid_password, verify_password
from app.security_models import AppUser
from app.session import get_db

router = APIRouter(prefix='/api/v1/auth', tags=['Authentication'])


class RegisterPayload(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    email: str = Field(min_length=5, max_length=150, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    region: str = Field(min_length=2, max_length=80)
    password: SecretStr


@router.post('/register', status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload, db: Session = Depends(get_db)):
    password = payload.password.get_secret_value()
    if not valid_password(password):
        raise HTTPException(422, 'Password must have at least 12 chars with upper/lower/digit/symbol')
    email = payload.email.lower().strip()
    if db.scalar(select(AppUser.id).where(AppUser.email == email)) is not None or db.scalar(
        select(Customer.id).where(Customer.email == email)
    ) is not None:
        raise HTTPException(409, 'Email already registered')
    customer_id = uuid4()
    user_id = uuid4()
    db.add(Customer(id=customer_id, customer_code='BC-' + token_hex(9).upper(),
                    full_name=payload.full_name.strip(), email=email, region=payload.region.strip(),
                    onboarding_status='PENDING'))
    db.add(AppUser(id=user_id, email=email, password_hash=hash_password(password),
                   role='CUSTOMER', customer_id=customer_id))
    db.add(AuditEvent(correlation_id=uuid4(), actor_type='CUSTOMER', action='SELF_REGISTRATION',
                      entity_type='CUSTOMER', entity_id=customer_id, result='SUCCESS',
                      details={'synthetic': True, 'verification': 'PENDING'}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Registration conflict')
    return {'customer_id': str(customer_id), 'onboarding_status': 'PENDING',
            'message': 'Synthetic registration created; requires human review'}


@router.post('/token')
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    email = form.username.lower().strip()
    user = db.scalar(select(AppUser).where(AppUser.email == email))
    if user is None or not user.active or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, 'Invalid credentials', headers={'WWW-Authenticate': 'Bearer'})
    return {'access_token': create_token(user), 'token_type': 'bearer', 'expires_in': 1800}


@router.get('/me')
def me(user: AppUser = Depends(current_user)):
    return {'id': str(user.id), 'email': user.email, 'role': user.role,
            'customer_id': str(user.customer_id) if user.customer_id else None}
