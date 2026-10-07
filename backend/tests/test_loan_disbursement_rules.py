from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.services.loan_disbursement import next_business_disbursement_at


def test_next_business_disbursement_uses_lima_9am():
    approved = datetime(2026, 9, 30, 21, 3, tzinfo=timezone.utc)
    scheduled = next_business_disbursement_at(
        approved,
        delay_business_days=1,
        tz=ZoneInfo("America/Lima"),
        hour_local=9,
    )

    assert scheduled == datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)


def test_next_business_disbursement_skips_weekend():
    approved = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)  # viernes 15:00 Lima
    scheduled = next_business_disbursement_at(
        approved,
        delay_business_days=1,
        tz=ZoneInfo("America/Lima"),
        hour_local=9,
    )

    assert scheduled == datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)


def test_zero_day_never_schedules_in_the_past():
    approved = datetime(2026, 9, 30, 21, 3, tzinfo=timezone.utc)
    scheduled = next_business_disbursement_at(
        approved,
        delay_business_days=0,
        tz=ZoneInfo("America/Lima"),
        hour_local=9,
    )

    assert scheduled == approved
