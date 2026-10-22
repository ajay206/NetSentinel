"""Review 2026-10: flag dev-only secrets at start-up; refuse them with NS_STRICT_SECRETS=1.

Compose and Helm ship dev defaults so `make demo` works out of the box. That is fine on a
laptop with synthetic data, but anything shared should set real values. This check logs a
warning for every placeholder and, in strict mode, stops the gateway from starting.
Values are never logged, only the variable names.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("api_gateway.secrets")

CHECKED = (
    "JWT_SECRET",
    "GATEWAY_SERVICE_TOKEN",
    "TICKET_SERVICE_TOKEN",
    "INCIDENT_SERVICE_TOKEN",
    "POSTGRES_PASSWORD",
)
_PLACEHOLDERS = ("dev-only", "change-me", "changeme")


def placeholder_secrets(env: dict[str, str] | None = None) -> list[str]:
    env = dict(os.environ) if env is None else env
    out = []
    for name in CHECKED:
        val = (env.get(name) or "").lower()
        if val and any(p in val for p in _PLACEHOLDERS):
            out.append(name)
    return out


def check(env: dict[str, str] | None = None) -> list[str]:
    env = dict(os.environ) if env is None else env
    found = placeholder_secrets(env)
    if found:
        logger.warning("dev-only placeholder secrets in use: %s (set real values in .env)", found)
        if env.get("NS_STRICT_SECRETS") == "1":
            raise RuntimeError(f"NS_STRICT_SECRETS=1 but placeholder secrets are set: {found}")
    return found
