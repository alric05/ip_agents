"""Tests for the Derwent JWT pre-flight utility."""

from __future__ import annotations

import base64
import json
import time

import pytest

from src.tools.clients.derwent_auth import (
    DerwentAuthError,
    check_derwent_jwt,
    decode_jwt_exp,
)


def _make_jwt(payload: dict) -> str:
    """Forge a JWT-shaped string with the given payload. Signature is junk."""
    header_b64 = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"{header_b64}.{payload_b64}.sig"


class TestDecodeJwtExp:
    def test_extracts_exp_claim(self):
        token = _make_jwt({"exp": 1700000000, "sub": "test"})
        assert decode_jwt_exp(token) == 1700000000

    def test_returns_none_when_not_jwt_shaped(self):
        assert decode_jwt_exp("not-a-jwt") is None
        assert decode_jwt_exp("a.b") is None
        assert decode_jwt_exp("") is None

    def test_returns_none_when_no_exp_claim(self):
        token = _make_jwt({"sub": "test"})
        assert decode_jwt_exp(token) is None

    def test_returns_none_on_corrupt_payload(self):
        token = "aaa.not-base64!!.sig"
        assert decode_jwt_exp(token) is None


class TestCheckDerwentJwt:
    def test_raises_on_missing_token(self, monkeypatch):
        monkeypatch.delenv("DERWENT_JWT_TOKEN", raising=False)
        with pytest.raises(DerwentAuthError, match="Derwent JWT not found"):
            check_derwent_jwt()

    def test_raises_on_expired_token(self):
        past = int(time.time()) - 3600
        token = _make_jwt({"exp": past})
        with pytest.raises(DerwentAuthError, match="expired"):
            check_derwent_jwt(token)

    def test_raises_when_expiring_within_skew(self):
        soon = int(time.time()) + 30
        token = _make_jwt({"exp": soon})
        with pytest.raises(DerwentAuthError, match="expires in"):
            check_derwent_jwt(token, skew_seconds=60)

    def test_passes_on_valid_token(self):
        future = int(time.time()) + 3600
        token = _make_jwt({"exp": future})
        check_derwent_jwt(token)  # must not raise

    def test_reads_env_var_when_no_token_arg(self, monkeypatch):
        future = int(time.time()) + 3600
        token = _make_jwt({"exp": future})
        monkeypatch.setenv("DERWENT_JWT_TOKEN", token)
        check_derwent_jwt()  # must not raise

    def test_passes_on_non_jwt_token(self, caplog):
        # Opaque token (not JWT-shaped) — can't pre-check locally, skip.
        check_derwent_jwt("opaque-token")  # must not raise
        assert any(
            "skipping local expiry check" in r.message for r in caplog.records
        )

    def test_error_message_names_env_var(self, monkeypatch):
        monkeypatch.delenv("DERWENT_JWT_TOKEN", raising=False)
        with pytest.raises(DerwentAuthError, match="DERWENT_JWT_TOKEN"):
            check_derwent_jwt()
