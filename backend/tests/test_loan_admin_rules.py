from datetime import date
from decimal import Decimal

import pytest

from app.services.loan_rules import add_months, build_installment_schedule, fixed_payment


def test_add_months_handles_end_of_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_fixed_payment_is_positive_and_cent_rounded():
    payment = fixed_payment(Decimal("5000.00"), Decimal("18.0000"), 12)
    assert payment > Decimal("0")
    assert payment == payment.quantize(Decimal("0.01"))


def test_schedule_has_expected_installment_count_and_due_dates():
    schedule = build_installment_schedule(
        Decimal("5000.00"),
        Decimal("18.0000"),
        12,
        date(2026, 9, 24),
    )
    assert len(schedule) == 12
    assert schedule[0][0] == 1
    assert schedule[0][1] == date(2026, 10, 24)
    assert schedule[-1][0] == 12
    assert schedule[-1][1] == date(2027, 9, 24)


@pytest.mark.parametrize("bad_rate", ["0", "-1", "100.0001"])
def test_invalid_tea_is_rejected(bad_rate):
    with pytest.raises(ValueError):
        fixed_payment(Decimal("5000.00"), Decimal(bad_rate), 12)
