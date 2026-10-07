from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def monthly_effective_rate(annual_effective_rate_percent: Decimal) -> Decimal:
    rate = Decimal(str(annual_effective_rate_percent))
    if not rate.is_finite() or rate <= 0 or rate > Decimal("100.0000"):
        raise ValueError("TEA must be greater than 0 and at most 100 percent")
    tea = float(rate / Decimal("100"))
    monthly = (1.0 + tea) ** (1.0 / 12.0) - 1.0
    return Decimal(str(monthly))


def fixed_payment(principal: Decimal, annual_effective_rate_percent: Decimal, term_months: int) -> Decimal:
    p = Decimal(str(principal))
    if not p.is_finite() or p <= 0:
        raise ValueError("Principal must be positive")
    if term_months not in {6, 12, 18, 24, 36, 48, 60}:
        raise ValueError("Unsupported loan term")

    r = monthly_effective_rate(annual_effective_rate_percent)
    factor = (Decimal("1") + r) ** term_months
    payment = p * r * factor / (factor - Decimal("1"))
    return payment.quantize(CENT, rounding=ROUND_HALF_UP)


def build_installment_schedule(
    principal: Decimal,
    annual_effective_rate_percent: Decimal,
    term_months: int,
    first_due_from: date,
) -> list[tuple[int, date, Decimal]]:
    payment = fixed_payment(principal, annual_effective_rate_percent, term_months)
    return [
        (number, add_months(first_due_from, number), payment)
        for number in range(1, term_months + 1)
    ]
