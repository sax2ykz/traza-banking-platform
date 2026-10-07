import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers.cards import require_local as cards_guard
from app.routers.loan_applications import require_local as loans_guard
from app.routers.operations import local_only as operations_guard


GUARDS = (
    cards_guard,
    loans_guard,
    operations_guard,
)


def remote_request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("10.20.30.40", 54321),
            "server": ("bancocloud.example", 443),
        }
    )


@pytest.mark.parametrize("guard", GUARDS)
def test_azure_environment_allows_remote_authenticated_routes(
    monkeypatch,
    guard,
):
    monkeypatch.setenv("APP_ENV", "azure")

    guard(remote_request())


@pytest.mark.parametrize("guard", GUARDS)
def test_local_environment_rejects_remote_requests(
    monkeypatch,
    guard,
):
    monkeypatch.setenv("APP_ENV", "local")

    with pytest.raises(HTTPException) as exc_info:
        guard(remote_request())

    assert exc_info.value.status_code == 403
