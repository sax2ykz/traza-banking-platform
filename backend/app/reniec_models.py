"""SQLAlchemy mappings for the synthetic RENIEC Simulator.

The database schema is created by database/004_reniec_simulator.sql.
This module does not create tables.
"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ReniecSimulatedRegistry(Base):
    __tablename__ = "reniec_simulated_registry"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    document_number: Mapped[str] = mapped_column(
        String(8),
        unique=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    birth_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    document_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    ubigeo: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
    )

    document_number: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    claimed_full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    claimed_birth_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    result: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    evidence_ref: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
    )

    registry_document_status: Mapped[str | None] = mapped_column(
        String(20),
    )

    matched_name: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )

    matched_birth_date: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )

    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )