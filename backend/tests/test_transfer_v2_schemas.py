from pydantic import ValidationError
import pytest
from uuid import uuid4

from app.services.transaction_schemas import (
    InterbankTransferRequest,
    ThirdPartyBeneficiaryRequest,
    ThirdPartyTransferRequest,
)


def test_third_party_account_number_validation():
    source = uuid4()

    request = ThirdPartyBeneficiaryRequest(
        source_account_id=source,
        target_account_number="BC1234567890ABCDEF12",
    )

    assert request.target_account_number == "BC1234567890ABCDEF12"

    with pytest.raises(ValidationError):
        ThirdPartyBeneficiaryRequest(
            source_account_id=source,
            target_account_number="cuenta con espacios",
        )


def test_third_party_transfer_contract():
    payload = ThirdPartyTransferRequest(
        source_account_id=uuid4(),
        target_account_number="BC1234567890ABCDEF12",
        amount="150.00",
        currency="PEN",
        idempotency_key="WEB-THIRD-0001",
    )

    assert str(payload.amount) == "150.00"
    assert payload.currency == "PEN"


def test_interbank_transfer_requires_twenty_digit_cci_and_known_bank():
    valid = InterbankTransferRequest(
        source_account_id=uuid4(),
        cci="00212345678901234567",
        destination_bank="BCP",
        amount="100.00",
        currency="PEN",
        idempotency_key="WEB-INTERBANK-0001",
    )

    assert valid.cci.endswith("4567")

    with pytest.raises(ValidationError):
        InterbankTransferRequest(
            source_account_id=uuid4(),
            cci="1234",
            destination_bank="BCP",
            amount="100.00",
            currency="PEN",
            idempotency_key="WEB-INTERBANK-0002",
        )

    with pytest.raises(ValidationError):
        InterbankTransferRequest(
            source_account_id=uuid4(),
            cci="00212345678901234567",
            destination_bank="OTRO",
            amount="100.00",
            currency="PEN",
            idempotency_key="WEB-INTERBANK-0003",
        )
