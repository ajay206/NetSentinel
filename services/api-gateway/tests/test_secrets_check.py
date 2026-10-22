"""Review 2026-10: dev-only secrets are flagged, and refused in strict mode."""

import pytest
from api_gateway import secrets_check


def test_flags_placeholders_by_name_only():
    env = {"JWT_SECRET": "dev-only-change-me-0123", "TICKET_SERVICE_TOKEN": "s3cr3t-real-value"}
    assert secrets_check.check(env) == ["JWT_SECRET"]


def test_strict_mode_refuses_placeholders():
    env = {"GATEWAY_SERVICE_TOKEN": "change-me", "NS_STRICT_SECRETS": "1"}
    with pytest.raises(RuntimeError, match="GATEWAY_SERVICE_TOKEN"):
        secrets_check.check(env)


def test_strict_mode_passes_real_values():
    env = {"JWT_SECRET": "x" * 40, "NS_STRICT_SECRETS": "1"}
    assert secrets_check.check(env) == []
