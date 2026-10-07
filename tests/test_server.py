import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from payments_mcp import server
from payments_mcp.auth import READ_SCOPE, WRITE_SCOPE, issue_token
from payments_mcp.ledger import Ledger

SECRET = "s" * 40


@pytest.fixture(autouse=True)
def fresh_ledger(monkeypatch):
    monkeypatch.setattr(server, "ledger", Ledger())


def call(tool: str, args: dict):
    async def run():
        async with Client(server.mcp) as client:
            return await client.call_tool(tool, args)

    return asyncio.run(run())


def test_tools_are_registered():
    async def run():
        async with Client(server.mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert asyncio.run(run()) == {"create_payment", "get_payment", "refund_payment"}


def test_create_get_refund_flow(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    created = call(
        "create_payment",
        {"amount": "20.00", "currency": "USD", "idempotency_key": "k1", "description": "demo"},
    ).data
    payment_id = created["payment"]["id"]
    assert created["created"] is True

    fetched = call("get_payment", {"payment_id": payment_id}).data
    assert fetched["status"] == "succeeded"

    refunded = call("refund_payment", {"payment_id": payment_id, "amount": "5.00"}).data
    assert refunded["status"] == "partially_refunded"


def test_retry_with_same_key_does_not_duplicate(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    args = {"amount": "9.99", "currency": "EUR", "idempotency_key": "same"}
    first = call("create_payment", args).data
    second = call("create_payment", args).data
    assert second["created"] is False
    assert first["payment"]["id"] == second["payment"]["id"]


def test_ledger_errors_surface_as_tool_errors(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    with pytest.raises(ToolError, match="amount must be greater than 0"):
        call("create_payment", {"amount": "-1", "currency": "USD", "idempotency_key": "k"})


def test_auth_is_required_by_default(monkeypatch):
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("PAYMENTS_JWT_SECRET", SECRET)
    with pytest.raises(ToolError, match="unauthorized"):
        call("get_payment", {"payment_id": "pay_x"})


def _with_header(monkeypatch, token: str):
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("PAYMENTS_JWT_SECRET", SECRET)
    monkeypatch.setattr(
        server, "get_http_headers", lambda **_: {"authorization": f"Bearer {token}"}
    )


def test_read_scope_cannot_write(monkeypatch):
    _with_header(monkeypatch, issue_token(SECRET, "agent", [READ_SCOPE]))
    with pytest.raises(ToolError, match="missing required scope"):
        call("create_payment", {"amount": "5.00", "currency": "USD", "idempotency_key": "k"})


def test_write_scope_can_write(monkeypatch):
    _with_header(monkeypatch, issue_token(SECRET, "agent", [WRITE_SCOPE]))
    result = call("create_payment", {"amount": "5.00", "currency": "USD", "idempotency_key": "k"})
    assert result.data["created"] is True
