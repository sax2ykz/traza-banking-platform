"""Separate metadata preserves the historical 11 banking-model regression tests.
Database constraints and foreign keys are defined by migration 003, not create_all.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SecurityBase(DeclarativeBase):
    pass


class AppUser(SecurityBase):
    __tablename__ = 'app_users'
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # SQL migration enforces FK and one-to-one relationship.
    customer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('TRUE'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('NOW()'))


class OnboardingReview(SecurityBase):
    __tablename__ = 'onboarding_reviews'
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    customer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reviewer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(15), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    document_checked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    data_consistent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(String(250), nullable=False, server_default=text("''"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('NOW()'))
