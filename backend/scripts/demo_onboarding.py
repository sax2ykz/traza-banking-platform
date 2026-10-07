"""BancoCloud: local-only integration demonstration, synthetic data ONLY.

Exercises real HTTP API + local staff action through SQLAlchemy. The staff
transition is a LOCAL DEVELOPMENT SIMULATION; it is NOT a verified real KYC
review and must never be used as the public/cloud onboarding mechanism.
"""
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

# Run from backend/; use its existing local app and local .env-based DB engine.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import AuditEvent, Customer  # noqa: E402
from app.session import SessionLocal  # noqa: E402

API = "http://127.0.0.1:8000"


def require(response: httpx.Response, expected: int, description: str):
    if response.status_code != expected:
        raise RuntimeError(
            f"{description}: se esperaba HTTP {expected}; se recibió "
            f"{response.status_code}: {response.text[:400]}"
        )
    print(f"[OK] {description}: HTTP {expected}")
    return response.json() if response.content else {}


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "--solo-local-sintetico":
        sys.exit("Uso: python scripts/demo_onboarding.py --solo-local-sintetico")

    suffix = uuid4().hex[:10].upper()
    customer_payload = {
        "customer_code": f"BC-DEMO-{suffix}",
        "full_name": "Cliente Sintetico de Prueba",
        "email": f"demo-{suffix.lower()}@example.invalid",
        "region": "Lima",
    }
    with httpx.Client(base_url=API, timeout=10) as client:
        status = require(client.get("/health/db"), 200, "API y PostgreSQL disponibles")
        if status.get("connection") != "OK":
            raise RuntimeError("/health/db no confirmó la conexión")

        customer = require(
            client.post("/api/v1/customers", json=customer_payload),
            201,
            "Registro de cliente sintético",
        )
        customer_id = UUID(customer["id"])
        assert customer["onboarding_status"] == "PENDING", customer
        print("[OK] Cliente inicia con onboarding PENDING")

        require(
            client.post("/api/v1/customers", json=customer_payload),
            409,
            "No se permite registro duplicado",
        )

        account_payload = {
            "customer_id": str(customer_id),
            "account_type": "SAVINGS",
            "currency": "PEN",
        }
        require(
            client.post("/api/v1/accounts", json=account_payload),
            409,
            "Cuenta rechazada mientras onboarding está PENDING",
        )
        invalid_payload = dict(account_payload, currency="XYZ")
        require(
            client.post("/api/v1/accounts", json=invalid_payload),
            422,
            "Se rechaza una moneda no admitida",
        )

        # LOCAL developer/staff simulation: no documents, PEP, sanctions,
        # national ID or actual customer identification are verified here.
        with SessionLocal.begin() as db:
            db_customer = db.get(Customer, customer_id, with_for_update=True)
            if db_customer is None or db_customer.onboarding_status != "PENDING":
                raise RuntimeError("El estado del cliente cambió inesperadamente")
            db_customer.onboarding_status = "VERIFIED"
            db.add(AuditEvent(
                correlation_id=uuid4(),
                actor_type="STAFF",
                action="DEV_SYNTHETIC_ONBOARDING_REVIEW",
                entity_type="CUSTOMER",
                entity_id=customer_id,
                result="SUCCESS",
                details={
                    "environment": "local-dev",
                    "simulated": True,
                    "real_kyc_performed": False,
                },
            ))
        print("[OK] Simulación LOCAL de revisión humana registrada con evento de auditoría")

        updated = require(
            client.get(f"/api/v1/customers/{customer_id}"),
            200,
            "Consulta de cliente tras revisión sintética",
        )
        assert updated["onboarding_status"] == "VERIFIED", updated

        account = require(
            client.post("/api/v1/accounts", json=account_payload),
            201,
            "Apertura de cuenta tras revisión sintética",
        )
        account_id = UUID(account["id"])
        assert Decimal(str(account["balance"])) == Decimal("0"), account
        assert account["currency"] == "PEN", account
        print("[OK] Cuenta creada con saldo inicial S/ 0,00")

        persisted = require(
            client.get(f"/api/v1/accounts/{account_id}"),
            200,
            "Consulta de cuenta persistida",
        )
        assert persisted["id"] == str(account_id), persisted

        with SessionLocal() as db:
            event = db.scalar(select(AuditEvent).where(
                AuditEvent.entity_id == customer_id,
                AuditEvent.action == "DEV_SYNTHETIC_ONBOARDING_REVIEW",
            ))
            assert event is not None and event.details["real_kyc_performed"] is False
        print("[OK] Evento de revisión sintética almacenado en audit_events")

    print("\nRESULTADO: DEMOSTRACIÓN LOCAL COMPLETADA")
    print(f"ID de cliente sintético: {customer_id}")
    print(f"ID de cuenta sintética: {account_id}")
    print("IMPORTANTE: la aprobación es SIMULADA; no constituye KYC real.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, httpx.HTTPError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
