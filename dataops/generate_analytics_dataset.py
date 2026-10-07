from __future__ import annotations

import calendar
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.session import SessionLocal  # noqa: E402


DATASET_VERSION = "analytics-v1"
SEED = 20260926
CUSTOMER_COUNT = 400
LOAN_COUNT = 120

PERIOD_START = date(2025, 9, 1)
PERIOD_END = date(2026, 8, 31)
SNAPSHOT_DATE = PERIOD_END

DATE_DIM_START = date(2025, 1, 1)
DATE_DIM_END = date(2029, 12, 31)

rng = random.Random(SEED)

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def stable_uuid(kind: str, value: str | int) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"bancocloud:{DATASET_VERSION}:{kind}:{value}",
    )


def money(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def rate(value: float) -> Decimal:
    return Decimal(f"{value:.4f}")


def date_key(value: date) -> int:
    return int(value.strftime("%Y%m%d"))


def random_date(start: date, end: date) -> date:
    if end < start:
        return start

    days = (end - start).days
    return start + timedelta(days=rng.randint(0, days))


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months

    year = value.year + month_index // 12
    month = month_index % 12 + 1

    day = min(
        value.day,
        calendar.monthrange(year, month)[1],
    )

    return date(year, month, day)


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def month_end(value: date) -> date:
    return add_months(month_start(value), 1) - timedelta(days=1)


def weighted_choice(
    options: list[tuple[Any, float]],
) -> Any:
    total = sum(weight for _, weight in options)
    target = rng.random() * total

    cumulative = 0.0

    for value, weight in options:
        cumulative += weight

        if target <= cumulative:
            return value

    return options[-1][0]


def delinquency_bucket(days: int) -> str:
    if days <= 0:
        return "AL_DIA"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_PLUS"


def months_elapsed(start: date, end: date) -> int:
    return max(
        0,
        (end.year - start.year) * 12
        + end.month
        - start.month,
    )


def monthly_payment(
    principal: float,
    annual_rate: float,
    term_months: int,
) -> float:
    monthly_rate = annual_rate / 100 / 12

    if monthly_rate == 0:
        return principal / term_months

    factor = (1 + monthly_rate) ** term_months

    return (
        principal
        * monthly_rate
        * factor
        / (factor - 1)
    )


def deposit_product(
    customer_id: UUID,
    segment: str,
) -> str:
    score = customer_id.int % 100

    threshold = {
        "MASIVO": 72,
        "PREFERENTE": 55,
        "PYME": 30,
    }[segment]

    return "SAVINGS" if score < threshold else "CHECKING"


def transaction_amount(
    segment: str,
    operation_type: str,
) -> float:
    ranges = {
        "MASIVO": {
            "DEPOSIT": (50, 1200, 220),
            "WITHDRAWAL": (20, 600, 120),
            "TRANSFER": (20, 1500, 250),
        },
        "PREFERENTE": {
            "DEPOSIT": (100, 3000, 650),
            "WITHDRAWAL": (50, 1200, 250),
            "TRANSFER": (50, 4000, 700),
        },
        "PYME": {
            "DEPOSIT": (300, 7000, 1800),
            "WITHDRAWAL": (100, 2500, 600),
            "TRANSFER": (200, 10000, 2500),
        },
    }

    low, high, mode = ranges[segment][operation_type]

    return round(
        rng.triangular(low, high, mode),
        2,
    )


def principal_amount(segment: str) -> float:
    ranges = {
        "MASIVO": (1500, 12000, 4500),
        "PREFERENTE": (5000, 25000, 11000),
        "PYME": (8000, 40000, 18000),
    }

    low, high, mode = ranges[segment]

    return round(
        rng.triangular(low, high, mode),
        2,
    )


def annual_rate(segment: str) -> float:
    ranges = {
        "MASIVO": (18.0, 32.0),
        "PREFERENTE": (12.0, 24.0),
        "PYME": (14.0, 28.0),
    }

    low, high = ranges[segment]

    return round(rng.uniform(low, high), 4)


def generate_dates() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    current = DATE_DIM_START

    while current <= DATE_DIM_END:
        result.append(
            {
                "date_key": date_key(current),
                "full_date": current,
                "year": current.year,
                "quarter": ((current.month - 1) // 3) + 1,
                "month": current.month,
                "month_name": MONTH_NAMES[current.month],
                "day": current.day,
                "weekday": current.isoweekday(),
                "is_weekend": current.isoweekday() in (6, 7),
            }
        )

        current += timedelta(days=1)

    return result


def generate_customers() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for index in range(1, CUSTOMER_COUNT + 1):
        customer_id = stable_uuid("customer", index)

        region = weighted_choice(
            [
                ("LIMA", 55),
                ("NORTE", 18),
                ("CENTRO", 12),
                ("SUR", 15),
            ]
        )

        segment = weighted_choice(
            [
                ("MASIVO", 68),
                ("PREFERENTE", 20),
                ("PYME", 12),
            ]
        )

        onboarding_date = random_date(
            date(2025, 1, 1),
            date(2026, 5, 31),
        )

        result.append(
            {
                "customer_id": customer_id,
                "customer_code": f"SYN-{index:04d}",
                "onboarding_date_key": date_key(onboarding_date),
                "onboarding_date": onboarding_date,
                "region": region,
                "segment": segment,
                "active": rng.random() < 0.97,
                "dataset_version": DATASET_VERSION,
            }
        )

    return result


def generate_transactions(
    customers: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    db_rows: list[dict[str, Any]] = []
    analytical_rows: list[dict[str, Any]] = []

    counter = 1

    for customer in customers:
        segment = customer["segment"]

        tx_range = {
            "MASIVO": (7, 13),
            "PREFERENTE": (10, 18),
            "PYME": (12, 22),
        }[segment]

        transaction_count = rng.randint(
            tx_range[0],
            tx_range[1],
        )

        active_start = max(
            PERIOD_START,
            customer["onboarding_date"],
        )

        if active_start > PERIOD_END:
            continue

        product = deposit_product(
            customer["customer_id"],
            segment,
        )

        for _ in range(transaction_count):
            tx_id = stable_uuid(
                "transaction",
                counter,
            )

            counter += 1

            tx_date = random_date(
                active_start,
                PERIOD_END,
            )

            operation_type = weighted_choice(
                [
                    ("TRANSFER", 50),
                    ("DEPOSIT", 30),
                    ("WITHDRAWAL", 20),
                ]
            )

            channel = weighted_choice(
                [
                    ("MOBILE", 55),
                    ("WEB", 20),
                    ("ATM", 18),
                    ("BRANCH", 7),
                ]
            )

            status = weighted_choice(
                [
                    ("COMPLETED", 96),
                    ("REJECTED", 4),
                ]
            )

            amount_value = transaction_amount(
                segment,
                operation_type,
            )

            fee_value = 0.0

            if status == "COMPLETED":
                if operation_type == "TRANSFER":
                    fee_value += rng.choice(
                        [0.0, 0.0, 0.5, 1.0, 1.5, 2.0]
                    )

                if channel == "ATM":
                    fee_value += rng.choice(
                        [0.0, 0.0, 1.0, 2.0]
                    )

                if channel == "BRANCH":
                    fee_value += rng.choice(
                        [0.0, 1.0, 2.0, 3.0]
                    )

            db_row = {
                "transaction_id": tx_id,
                "customer_id": customer["customer_id"],
                "date_key": date_key(tx_date),
                "operation_type": operation_type,
                "channel": channel,
                "status": status,
                "amount": money(amount_value),
                "fee_amount": money(fee_value),
                "currency": "PEN",
                "dataset_version": DATASET_VERSION,
            }

            db_rows.append(db_row)

            analytical_rows.append(
                {
                    **db_row,
                    "transaction_date": tx_date,
                    "segment": segment,
                    "product": product,
                }
            )

    return db_rows, analytical_rows


def choose_target_installment(
    schedule: list[tuple[int, date]],
    target_bucket: str,
) -> int | None:
    if target_bucket == "AL_DIA":
        return None

    eligible: list[int] = []

    for number, due_date in schedule:
        if due_date > SNAPSHOT_DATE:
            continue

        dpd = (SNAPSHOT_DATE - due_date).days

        if delinquency_bucket(dpd) == target_bucket:
            eligible.append(number)

    if not eligible:
        return None

    return eligible[0]


def generate_loans(
    customers: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    selected = rng.sample(
        customers,
        LOAN_COUNT,
    )

    loan_rows: list[dict[str, Any]] = []
    installment_rows: list[dict[str, Any]] = []
    analytical_loans: list[dict[str, Any]] = []

    fixture_buckets = [
        ("1_30", 15),
        ("31_60", 45),
        ("61_90", 75),
        ("90_PLUS", 120),
    ]

    installment_counter = 1

    for index, customer in enumerate(selected, start=1):
        loan_id = stable_uuid(
            "loan",
            index,
        )

        segment = customer["segment"]

        principal = principal_amount(segment)
        annual = annual_rate(segment)

        if index <= len(fixture_buckets):
            target_bucket, target_dpd = fixture_buckets[index - 1]

            target_due = SNAPSHOT_DATE - timedelta(
                days=target_dpd
            )

            origination = add_months(
                target_due,
                -1,
            )

            term = 12

        else:
            origination = random_date(
                PERIOD_START,
                date(2026, 5, 31),
            )

            term = weighted_choice(
                [
                    (6, 15),
                    (12, 35),
                    (18, 15),
                    (24, 25),
                    (36, 10),
                ]
            )

            target_bucket = weighted_choice(
                [
                    ("AL_DIA", 74),
                    ("1_30", 10),
                    ("31_60", 7),
                    ("61_90", 5),
                    ("90_PLUS", 4),
                ]
            )

        payment = monthly_payment(
            principal,
            annual,
            term,
        )

        schedule = [
            (
                number,
                add_months(origination, number),
            )
            for number in range(1, term + 1)
        ]

        if index <= len(fixture_buckets):
            target_installment = 1
        else:
            target_installment = choose_target_installment(
                schedule,
                target_bucket,
            )

        fully_paid_installments = 0
        has_delinquency = False

        local_installments: list[dict[str, Any]] = []

        for number, due_date in schedule:
            due_value = money(payment)

            paid_date: date | None = None
            paid_value = Decimal("0.00")
            outstanding = due_value
            dpd = 0
            bucket = "AL_DIA"
            status = "PENDING"

            if due_date <= SNAPSHOT_DATE:
                if (
                    target_installment is None
                    or number < target_installment
                ):
                    paid_value = due_value
                    outstanding = Decimal("0.00")
                    status = "PAID"

                    paid_date = min(
                        due_date
                        + timedelta(
                            days=rng.randint(0, 5)
                        ),
                        SNAPSHOT_DATE,
                    )

                    fully_paid_installments += 1

                else:
                    has_delinquency = True

                    dpd = (
                        SNAPSHOT_DATE - due_date
                    ).days

                    bucket = delinquency_bucket(dpd)

                    if (
                        number == target_installment
                        and rng.random() < 0.45
                    ):
                        fraction = rng.uniform(
                            0.35,
                            0.70,
                        )

                        paid_value = money(
                            float(due_value) * fraction
                        )

                        outstanding = (
                            due_value - paid_value
                        )

                        status = "PARTIAL"

                        paid_date = min(
                            due_date
                            + timedelta(
                                days=rng.randint(1, 7)
                            ),
                            SNAPSHOT_DATE,
                        )

                    else:
                        paid_value = Decimal("0.00")
                        outstanding = due_value
                        status = "OVERDUE"

            installment_id = stable_uuid(
                "installment",
                installment_counter,
            )

            installment_counter += 1

            row = {
                "installment_id": installment_id,
                "loan_id": loan_id,
                "installment_number": number,
                "due_date_key": date_key(due_date),
                "paid_date_key": (
                    date_key(paid_date)
                    if paid_date is not None
                    else None
                ),
                "due_amount": due_value,
                "paid_amount": paid_value,
                "outstanding_amount": outstanding,
                "days_past_due": dpd,
                "delinquency_bucket": bucket,
                "status": status,
                "dataset_version": DATASET_VERSION,
            }

            local_installments.append(row)

        remaining_ratio = max(
            term - fully_paid_installments,
            0,
        ) / term

        current_balance = money(
            principal * remaining_ratio
        )

        last_due_date = schedule[-1][1]

        if (
            last_due_date <= SNAPSHOT_DATE
            and not has_delinquency
        ):
            loan_status = "CLOSED"
            current_balance = Decimal("0.00")

        elif has_delinquency:
            loan_status = "DELINQUENT"

        else:
            loan_status = "ACTIVE"

        loan_row = {
            "loan_id": loan_id,
            "customer_id": customer["customer_id"],
            "origination_date_key": date_key(origination),
            "principal": money(principal),
            "annual_rate": rate(annual),
            "term_months": term,
            "current_balance": current_balance,
            "status": loan_status,
            "dataset_version": DATASET_VERSION,
        }

        loan_rows.append(loan_row)
        installment_rows.extend(local_installments)

        analytical_loans.append(
            {
                **loan_row,
                "origination_date": origination,
                "segment": segment,
            }
        )

    return (
        loan_rows,
        installment_rows,
        analytical_loans,
    )


def generate_profitability(
    customers: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    loans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    customers_by_id = {
        customer["customer_id"]: customer
        for customer in customers
    }

    period = month_start(PERIOD_START)

    while period <= PERIOD_END:
        end = min(
            month_end(period),
            PERIOD_END,
        )

        for segment in (
            "MASIVO",
            "PREFERENTE",
            "PYME",
        ):
            segment_customers = [
                customer
                for customer in customers
                if customer["segment"] == segment
                and customer["onboarding_date"] <= end
            ]

            for product in (
                "SAVINGS",
                "CHECKING",
            ):
                product_customers = [
                    customer
                    for customer in segment_customers
                    if deposit_product(
                        customer["customer_id"],
                        segment,
                    )
                    == product
                ]

                customer_ids = {
                    customer["customer_id"]
                    for customer in product_customers
                }

                monthly_transactions = [
                    tx
                    for tx in transactions
                    if tx["segment"] == segment
                    and tx["product"] == product
                    and tx["status"] == "COMPLETED"
                    and month_start(
                        tx["transaction_date"]
                    )
                    == period
                ]

                tx_count = len(
                    monthly_transactions
                )

                tx_amount = sum(
                    float(tx["amount"])
                    for tx in monthly_transactions
                )

                fees = sum(
                    float(tx["fee_amount"])
                    for tx in monthly_transactions
                )

                if product == "SAVINGS":
                    funding_cost = (
                        tx_amount * 0.00015
                    )

                    operating_cost = (
                        len(customer_ids) * 1.20
                        + tx_count * 0.04
                    )

                else:
                    funding_cost = (
                        tx_amount * 0.00010
                    )

                    operating_cost = (
                        len(customer_ids) * 1.60
                        + tx_count * 0.06
                    )

                result.append(
                    {
                        "period_month_key": date_key(
                            period
                        ),
                        "segment": segment,
                        "product": product,
                        "active_customers": len(
                            customer_ids
                        ),
                        "transaction_count": tx_count,
                        "transaction_amount": money(
                            tx_amount
                        ),
                        "outstanding_balance": Decimal(
                            "0.00"
                        ),
                        "interest_income": Decimal(
                            "0.00"
                        ),
                        "fee_income": money(fees),
                        "funding_cost": money(
                            funding_cost
                        ),
                        "allocated_operating_cost": money(
                            operating_cost
                        ),
                        "dataset_version": DATASET_VERSION,
                    }
                )

            monthly_loans = [
                loan
                for loan in loans
                if loan["segment"] == segment
                and loan["origination_date"] <= end
            ]

            outstanding_total = 0.0
            weighted_interest = 0.0
            loan_customer_ids: set[UUID] = set()

            new_principal = 0.0

            for loan in monthly_loans:
                loan_customer_ids.add(
                    loan["customer_id"]
                )

                elapsed = months_elapsed(
                    loan["origination_date"],
                    end,
                )

                remaining = max(
                    loan["term_months"] - elapsed,
                    0,
                )

                balance = (
                    float(loan["principal"])
                    * remaining
                    / loan["term_months"]
                )

                outstanding_total += balance

                weighted_interest += (
                    balance
                    * float(loan["annual_rate"])
                    / 100
                    / 12
                )

                if month_start(
                    loan["origination_date"]
                ) == period:
                    new_principal += float(
                        loan["principal"]
                    )

            funding_cost = (
                outstanding_total * 0.006
            )

            operating_cost = (
                len(monthly_loans) * 3.50
            )

            origination_fee = (
                new_principal * 0.0025
            )

            result.append(
                {
                    "period_month_key": date_key(
                        period
                    ),
                    "segment": segment,
                    "product": "CONSUMER_LOAN",
                    "active_customers": len(
                        loan_customer_ids
                    ),
                    "transaction_count": 0,
                    "transaction_amount": Decimal(
                        "0.00"
                    ),
                    "outstanding_balance": money(
                        outstanding_total
                    ),
                    "interest_income": money(
                        weighted_interest
                    ),
                    "fee_income": money(
                        origination_fee
                    ),
                    "funding_cost": money(
                        funding_cost
                    ),
                    "allocated_operating_cost": money(
                        operating_cost
                    ),
                    "dataset_version": DATASET_VERSION,
                }
            )

        period = add_months(period, 1)

    return result


def main() -> None:
    dates = generate_dates()
    customers = generate_customers()

    transactions_db, transactions_analytical = (
        generate_transactions(customers)
    )

    (
        loans_db,
        installments_db,
        loans_analytical,
    ) = generate_loans(customers)

    profitability = generate_profitability(
        customers,
        transactions_analytical,
        loans_analytical,
    )

    customer_db_rows = [
        {
            key: value
            for key, value in customer.items()
            if key != "onboarding_date"
        }
        for customer in customers
    ]

    notes = (
        "Dataset 100% sintetico y reproducible para analitica academica. "
        "No contiene PII real. Periodo: ultimos 12 meses completos. "
        "Rentabilidad expresada como margen operativo estimado, no utilidad neta. "
        "Los costos e ingresos son supuestos sinteticos documentados en el generador."
    )

    with SessionLocal.begin() as db:

        # -----------------------------------------------------
        # REEJECUCION IDEMPOTENTE DE analytics-v1
        # -----------------------------------------------------

        db.execute(
            text(
                """
                DELETE FROM analytics.synthetic_profitability_monthly
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        db.execute(
            text(
                """
                DELETE FROM analytics.synthetic_loan_installments
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        db.execute(
            text(
                """
                DELETE FROM analytics.synthetic_transactions
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        db.execute(
            text(
                """
                DELETE FROM analytics.synthetic_loans
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        db.execute(
            text(
                """
                DELETE FROM analytics.synthetic_customers
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        db.execute(
            text(
                """
                DELETE FROM analytics.dataset_runs
                WHERE dataset_version = :version
                """
            ),
            {"version": DATASET_VERSION},
        )

        # -----------------------------------------------------
        # DIMENSION FECHA
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.dim_date (
                    date_key,
                    full_date,
                    year,
                    quarter,
                    month,
                    month_name,
                    day,
                    weekday,
                    is_weekend
                )
                VALUES (
                    :date_key,
                    :full_date,
                    :year,
                    :quarter,
                    :month,
                    :month_name,
                    :day,
                    :weekday,
                    :is_weekend
                )
                ON CONFLICT (full_date)
                DO NOTHING
                """
            ),
            dates,
        )

        # -----------------------------------------------------
        # METADATA
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.dataset_runs (
                    dataset_version,
                    seed,
                    period_start,
                    period_end,
                    requested_customers,
                    notes
                )
                VALUES (
                    :dataset_version,
                    :seed,
                    :period_start,
                    :period_end,
                    :requested_customers,
                    :notes
                )
                """
            ),
            {
                "dataset_version": DATASET_VERSION,
                "seed": SEED,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "requested_customers": CUSTOMER_COUNT,
                "notes": notes,
            },
        )

        # -----------------------------------------------------
        # CUSTOMERS
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.synthetic_customers (
                    customer_id,
                    customer_code,
                    onboarding_date_key,
                    region,
                    segment,
                    active,
                    dataset_version
                )
                VALUES (
                    :customer_id,
                    :customer_code,
                    :onboarding_date_key,
                    :region,
                    :segment,
                    :active,
                    :dataset_version
                )
                """
            ),
            customer_db_rows,
        )

        # -----------------------------------------------------
        # TRANSACTIONS
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.synthetic_transactions (
                    transaction_id,
                    customer_id,
                    date_key,
                    operation_type,
                    channel,
                    status,
                    amount,
                    fee_amount,
                    currency,
                    dataset_version
                )
                VALUES (
                    :transaction_id,
                    :customer_id,
                    :date_key,
                    :operation_type,
                    :channel,
                    :status,
                    :amount,
                    :fee_amount,
                    :currency,
                    :dataset_version
                )
                """
            ),
            transactions_db,
        )

        # -----------------------------------------------------
        # LOANS
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.synthetic_loans (
                    loan_id,
                    customer_id,
                    origination_date_key,
                    principal,
                    annual_rate,
                    term_months,
                    current_balance,
                    status,
                    dataset_version
                )
                VALUES (
                    :loan_id,
                    :customer_id,
                    :origination_date_key,
                    :principal,
                    :annual_rate,
                    :term_months,
                    :current_balance,
                    :status,
                    :dataset_version
                )
                """
            ),
            loans_db,
        )

        # -----------------------------------------------------
        # INSTALLMENTS
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.synthetic_loan_installments (
                    installment_id,
                    loan_id,
                    installment_number,
                    due_date_key,
                    paid_date_key,
                    due_amount,
                    paid_amount,
                    outstanding_amount,
                    days_past_due,
                    delinquency_bucket,
                    status,
                    dataset_version
                )
                VALUES (
                    :installment_id,
                    :loan_id,
                    :installment_number,
                    :due_date_key,
                    :paid_date_key,
                    :due_amount,
                    :paid_amount,
                    :outstanding_amount,
                    :days_past_due,
                    :delinquency_bucket,
                    :status,
                    :dataset_version
                )
                """
            ),
            installments_db,
        )

        # -----------------------------------------------------
        # PROFITABILITY
        # -----------------------------------------------------

        db.execute(
            text(
                """
                INSERT INTO analytics.synthetic_profitability_monthly (
                    period_month_key,
                    segment,
                    product,
                    active_customers,
                    transaction_count,
                    transaction_amount,
                    outstanding_balance,
                    interest_income,
                    fee_income,
                    funding_cost,
                    allocated_operating_cost,
                    dataset_version
                )
                VALUES (
                    :period_month_key,
                    :segment,
                    :product,
                    :active_customers,
                    :transaction_count,
                    :transaction_amount,
                    :outstanding_balance,
                    :interest_income,
                    :fee_income,
                    :funding_cost,
                    :allocated_operating_cost,
                    :dataset_version
                )
                """
            ),
            profitability,
        )

    print("=" * 72)
    print("BancoCloud - Synthetic Analytics Dataset")
    print("=" * 72)
    print(f"dataset_version       : {DATASET_VERSION}")
    print(f"seed                  : {SEED}")
    print(f"period                : {PERIOD_START} -> {PERIOD_END}")
    print(f"dim_date              : {len(dates)}")
    print(f"customers             : {len(customer_db_rows)}")
    print(f"transactions          : {len(transactions_db)}")
    print(f"loans                 : {len(loans_db)}")
    print(f"loan_installments     : {len(installments_db)}")
    print(f"profitability_monthly : {len(profitability)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
