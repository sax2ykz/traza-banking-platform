"""Authenticated synthetic BancoCloud dev API; no production identity assurance.
Keep Uvicorn bound to 127.0.0.1 until deployment hardening and threat review.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import check_database
from app.routers import (
    accounts,
    auth,
    cards,
    control_tower,
    copilot_admin,
    customer_loans,
    customers,
    loan_admin,
    loan_applications,
    onboarding_admin,
    onboarding_identity,
    operations,
)
from app.services.loan_disbursement import (
    auto_process_enabled,
    poll_seconds,
    process_due_loan_disbursements,
)

logger = logging.getLogger("bancocloud.loan_disbursement")

APP_ENV = os.getenv("APP_ENV", "local").strip().lower()

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


async def _loan_disbursement_loop(stop_event: asyncio.Event) -> None:
    """Retry-safe loop; App Service restarts simply re-run the catch-up scan."""

    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(process_due_loan_disbursements)
            if result.scheduled or result.processed or result.replayed or result.failed:
                logger.info(
                    "Loan disbursement cycle: scheduled=%s processed=%s replayed=%s failed=%s",
                    result.scheduled,
                    result.processed,
                    result.replayed,
                    result.failed,
                )
        except Exception:
            # A scheduler failure must not take the banking API down. The next
            # cycle retries from persisted state and deterministic idempotency.
            logger.exception("Loan disbursement cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds())
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    task: asyncio.Task[None] | None = None

    if auto_process_enabled():
        task = asyncio.create_task(_loan_disbursement_loop(stop_event))
        logger.info("Scheduled loan disbursement worker enabled")
    else:
        logger.info("Scheduled loan disbursement worker disabled")

    try:
        yield
    finally:
        if task is not None:
            stop_event.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="BancoCloud API",
    version="0.10.0",
    description=(
        "Authenticated synthetic BancoCloud academic environment; "
        "NOT a real KYC or production banking system."
    ),
    lifespan=lifespan,
)

if CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def environment_access_control(
    request: Request,
    call_next,
):
    if APP_ENV == "local":
        if (
            request.client is None
            or request.client.host
            not in {"127.0.0.1", "::1", "testclient"}
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Local development only"},
            )

    return await call_next(request)


for module in (
    control_tower,
    copilot_admin,
    auth,
    onboarding_identity,
    onboarding_admin,
    loan_admin,
    customer_loans,
    customers,
    accounts,
    operations,
    cards,
    loan_applications,
):
    app.include_router(module.router)


@app.get("/")
def root():
    return {
        "application": "BancoCloud",
        "status": "running",
        "environment": APP_ENV,
    }


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/health/db")
def database_health():
    try:
        check_database()

        return {
            "database": "PostgreSQL",
            "connection": "OK",
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable",
        )
