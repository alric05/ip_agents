"""Derwent JWT pre-flight check.

Decodes the JWT payload locally (no network call) and fails fast if the
token is missing, malformed, or expired. Wired into the eval runner and
CLI entrypoints so runs abort before any GT-dependent metric silently
collapses to 0.00 from a dead token.

This does NOT verify the JWT signature — we trust Derwent to do that on
every request. Local decode is only for catching the "user forgot to
refresh the token" failure mode cheaply before a multi-minute run starts.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)

_JWT_ENV_VAR = "DERWENT_JWT_TOKEN"
_DEFAULT_SKEW_SECONDS = 60


class DerwentAuthError(RuntimeError):
    """Raised when the Derwent JWT is missing, malformed, or expired."""


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_jwt_exp(token: str) -> int | None:
    """Return the `exp` (expiry) unix timestamp from a JWT payload.

    Returns None if the token is not JWT-shaped or has no `exp` claim.
    Never raises — callers decide what "no exp" means.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return int(exp)
    return None


def check_derwent_jwt(
    token: str | None = None,
    *,
    skew_seconds: int = _DEFAULT_SKEW_SECONDS,
) -> None:
    """Pre-flight: raise DerwentAuthError if the JWT is unusable.

    Args:
        token: JWT string to check. If None, reads DERWENT_JWT_TOKEN env var.
        skew_seconds: Treat tokens expiring within this many seconds as
            already expired — avoids starting a long run on a nearly-dead
            token. Default 60s.

    Raises:
        DerwentAuthError: token missing, malformed, or expired.
    """
    if token is None:
        token = os.environ.get(_JWT_ENV_VAR)

    if not token:
        raise DerwentAuthError(
            f"Derwent JWT not found. Set {_JWT_ENV_VAR} in your environment "
            "or provide a token via Authorization: Bearer <JWT>."
        )

    exp = decode_jwt_exp(token)
    if exp is None:
        # Not JWT-shaped or no exp claim. Can't pre-check locally — let the
        # first real request surface a 401 rather than blocking the run.
        _logger.warning(
            "Derwent token is not JWT-shaped or has no `exp` claim; "
            "skipping local expiry check."
        )
        return

    now = int(time.time())
    remaining = exp - now
    if remaining <= skew_seconds:
        exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
        if remaining <= 0:
            msg = f"Derwent JWT expired {-remaining}s ago (exp={exp_iso})."
        else:
            msg = (
                f"Derwent JWT expires in {remaining}s (exp={exp_iso}), "
                f"below safety skew of {skew_seconds}s."
            )
        raise DerwentAuthError(
            f"{msg} Refresh {_JWT_ENV_VAR} before starting the run "
            "or all Derwent-backed metrics will collapse to 0.00."
        )

    _logger.info(
        "Derwent JWT pre-flight OK — %ds remaining (exp=%s)",
        remaining,
        datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
    )
