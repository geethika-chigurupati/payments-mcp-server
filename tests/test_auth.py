import time

import jwt
import pytest

from payments_mcp.auth import (
    ALGORITHM,
    READ_SCOPE,
    WRITE_SCOPE,
    AuthError,
    claims_from_headers,
    issue_token,
    require_scope,
    verify_token,
)

SECRET = "x" * 40


def test_valid_token_round_trip():
    token = issue_token(SECRET, "agent-1", [READ_SCOPE])
    claims = verify_token(token, SECRET)
    assert claims["sub"] == "agent-1"
    assert claims["scope"] == READ_SCOPE


def test_wrong_secret_rejected():
    token = issue_token(SECRET, "agent-1", [READ_SCOPE])
    with pytest.raises(AuthError, match="invalid token"):
        verify_token(token, "y" * 40)


def test_expired_token_rejected():
    token = issue_token(SECRET, "agent-1", [READ_SCOPE], ttl_seconds=-10)
    with pytest.raises(AuthError, match="expired"):
        verify_token(token, SECRET)


def test_token_without_expiry_rejected():
    claims = {"iss": "payments-mcp-server", "sub": "agent-1", "scope": READ_SCOPE}
    token = jwt.encode(claims, SECRET, algorithm=ALGORITHM)
    with pytest.raises(AuthError):
        verify_token(token, SECRET)


def test_wrong_issuer_rejected():
    claims = {"iss": "someone-else", "sub": "a", "exp": int(time.time()) + 60}
    token = jwt.encode(claims, SECRET, algorithm=ALGORITHM)
    with pytest.raises(AuthError):
        verify_token(token, SECRET)


def test_unsigned_token_rejected():
    claims = {"iss": "payments-mcp-server", "sub": "a", "exp": int(time.time()) + 60}
    token = jwt.encode(claims, key=None, algorithm="none")
    with pytest.raises(AuthError):
        verify_token(token, SECRET)


def test_scope_check():
    claims = {"scope": f"{READ_SCOPE}"}
    require_scope(claims, READ_SCOPE)
    with pytest.raises(AuthError, match="missing required scope"):
        require_scope(claims, WRITE_SCOPE)


def test_headers_missing_or_malformed():
    for headers in ({}, {"authorization": "Token abc"}, {"authorization": "Bearer "}):
        with pytest.raises(AuthError, match="missing bearer token"):
            claims_from_headers(headers, SECRET)


def test_headers_with_valid_bearer_token():
    token = issue_token(SECRET, "agent-1", [WRITE_SCOPE])
    claims = claims_from_headers({"authorization": f"Bearer {token}"}, SECRET)
    assert claims["sub"] == "agent-1"
