from decimal import Decimal

import pytest

from payments_mcp.ledger import Ledger, PaymentError, parse_amount


@pytest.fixture
def ledger() -> Ledger:
    return Ledger()


def test_create_payment(ledger):
    payment, created = ledger.create_payment("19.99", "usd", "Order 1", "key-1")
    assert created is True
    assert payment.amount == Decimal("19.99")
    assert payment.currency == "USD"
    assert payment.status == "succeeded"
    assert payment.id.startswith("pay_")


def test_same_key_same_request_returns_original(ledger):
    first, created_first = ledger.create_payment("5.00", "USD", "x", "key-1")
    second, created_second = ledger.create_payment("5.00", "USD", "x", "key-1")
    assert created_first is True
    assert created_second is False
    assert first.id == second.id


def test_same_key_different_request_is_rejected(ledger):
    ledger.create_payment("5.00", "USD", "x", "key-1")
    with pytest.raises(PaymentError, match="different payment details"):
        ledger.create_payment("6.00", "USD", "x", "key-1")


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "1.234", "NaN", "Infinity", "2000000"])
def test_invalid_amounts_rejected(bad):
    with pytest.raises(PaymentError):
        parse_amount(bad)


def test_unsupported_currency_rejected(ledger):
    with pytest.raises(PaymentError, match="unsupported currency"):
        ledger.create_payment("5.00", "JPY", "", "key-1")


def test_idempotency_key_required(ledger):
    with pytest.raises(PaymentError, match="idempotency_key"):
        ledger.create_payment("5.00", "USD", "", "")


def test_get_unknown_payment(ledger):
    with pytest.raises(PaymentError, match="not found"):
        ledger.get_payment("pay_missing")


def test_partial_then_full_refund(ledger):
    payment, _ = ledger.create_payment("10.00", "USD", "", "key-1")
    after_partial = ledger.refund_payment(payment.id, "4.00")
    assert after_partial.status == "partially_refunded"
    assert after_partial.refunded_amount == Decimal("4.00")

    after_rest = ledger.refund_payment(payment.id)  # omit amount -> refund the remainder
    assert after_rest.status == "refunded"
    assert after_rest.refunded_amount == Decimal("10.00")


def test_refund_cannot_exceed_balance(ledger):
    payment, _ = ledger.create_payment("10.00", "USD", "", "key-1")
    ledger.refund_payment(payment.id, "7.00")
    with pytest.raises(PaymentError, match="exceeds"):
        ledger.refund_payment(payment.id, "3.01")


def test_fully_refunded_payment_cannot_be_refunded_again(ledger):
    payment, _ = ledger.create_payment("10.00", "USD", "", "key-1")
    ledger.refund_payment(payment.id)
    with pytest.raises(PaymentError, match="already fully refunded"):
        ledger.refund_payment(payment.id)
