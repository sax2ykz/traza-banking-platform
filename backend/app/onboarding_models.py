"""SQLAlchemy mappings for STP onboarding exception management.

The physical schema is created by database/008_onboarding_stp.sql.
This module does not create or migrate database tables.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OnboardingBase(DeclarativeBase):
    pass


class OnboardingExceptionCase(OnboardingBase):
    __tablename__ = "onboarding_exception_cases"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )

    identity_verification_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'OPEN'"),
    )

    reason: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        server_default=text("'MEDIUM'"),
    )

    severity: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
        server_default=text("'MEDIUM'"),
    )

    rule_version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    assigned_to: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    sla_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
