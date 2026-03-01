# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation
"""
Tests for pytest_governance assertion helpers.

The assertion functions require a live GovernanceEngine which is an optional
dependency. These tests exercise the assertion logic by mocking the engine
interface, validating that assertions raise AssertionError or pass as expected.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers to build mock engine and decision objects
# ---------------------------------------------------------------------------


def _make_decision(permitted: bool, reason: str = "test reason") -> MagicMock:
    decision = MagicMock()
    decision.permitted = permitted
    decision.reason = reason
    return decision


def _make_engine(
    check_sync_responses: list[MagicMock] | None = None,
    budget_check_response: MagicMock | None = None,
    audit_records: list[Any] | None = None,
) -> MagicMock:
    engine = MagicMock()

    if check_sync_responses is not None:
        engine.check_sync.side_effect = check_sync_responses

    if budget_check_response is not None:
        engine.budget.check.return_value = budget_check_response

    if audit_records is not None:
        engine.audit.query.return_value = audit_records

    engine.trust.set_level = MagicMock()
    return engine


# ---------------------------------------------------------------------------
# TestAssertTrustRequired
# ---------------------------------------------------------------------------


class TestAssertTrustRequired:
    def test_passes_when_boundary_is_correct(self) -> None:
        from pytest_governance.assertions import assert_trust_required

        # Side 1: denied at level-1; Side 2: permitted at level
        engine = _make_engine(
            check_sync_responses=[
                _make_decision(permitted=False),  # below required level: denied
                _make_decision(permitted=True),   # at required level: permitted
            ]
        )
        # Should not raise
        assert_trust_required(engine, action="file:write", required_level=3)

    def test_fails_when_action_permitted_below_required_level(self) -> None:
        from pytest_governance.assertions import assert_trust_required

        # Both responses are permitted (policy too permissive)
        engine = _make_engine(
            check_sync_responses=[
                _make_decision(permitted=True),  # wrongly permitted at level-1
                _make_decision(permitted=True),
            ]
        )
        with pytest.raises(AssertionError, match="permitted at L"):
            assert_trust_required(engine, action="file:write", required_level=3)

    def test_fails_when_action_denied_at_required_level(self) -> None:
        from pytest_governance.assertions import assert_trust_required

        engine = _make_engine(
            check_sync_responses=[
                _make_decision(permitted=False),  # correctly denied below
                _make_decision(permitted=False, reason="policy error"),  # wrongly denied at level
            ]
        )
        with pytest.raises(AssertionError, match="denied"):
            assert_trust_required(engine, action="file:write", required_level=3)

    def test_required_level_less_than_1_raises_value_error(self) -> None:
        from pytest_governance.assertions import assert_trust_required

        engine = _make_engine()
        with pytest.raises(ValueError, match="required_level must be >= 1"):
            assert_trust_required(engine, action="file:write", required_level=0)

    def test_set_level_called_with_correct_levels(self) -> None:
        from pytest_governance.assertions import assert_trust_required

        engine = _make_engine(
            check_sync_responses=[
                _make_decision(permitted=False),
                _make_decision(permitted=True),
            ]
        )
        assert_trust_required(engine, action="file:write", required_level=3, agent_id="agent-x")
        calls = engine.trust.set_level.call_args_list
        assert len(calls) == 2
        # First call: level - 1 = 2
        assert calls[0][0][1] == 2
        # Second call: level = 3
        assert calls[1][0][1] == 3


# ---------------------------------------------------------------------------
# TestAssertBudgetSufficient
# ---------------------------------------------------------------------------


class TestAssertBudgetSufficient:
    def test_passes_when_budget_sufficient(self) -> None:
        from pytest_governance.assertions import assert_budget_sufficient

        engine = _make_engine(budget_check_response=_make_decision(permitted=True))
        # Should not raise
        assert_budget_sufficient(engine, category="compute", amount=0.5)

    def test_fails_when_budget_insufficient(self) -> None:
        from pytest_governance.assertions import assert_budget_sufficient

        engine = _make_engine(
            budget_check_response=_make_decision(
                permitted=False, reason="Insufficient funds"
            )
        )
        with pytest.raises(AssertionError, match="Budget check failed"):
            assert_budget_sufficient(engine, category="compute", amount=100.0)


# ---------------------------------------------------------------------------
# TestAssertBudgetExceeded
# ---------------------------------------------------------------------------


class TestAssertBudgetExceeded:
    def test_passes_when_budget_exceeded(self) -> None:
        from pytest_governance.assertions import assert_budget_exceeded

        engine = _make_engine(budget_check_response=_make_decision(permitted=False))
        # Should not raise
        assert_budget_exceeded(engine, category="compute", amount=100.0)

    def test_fails_when_budget_unexpectedly_passes(self) -> None:
        from pytest_governance.assertions import assert_budget_exceeded

        engine = _make_engine(budget_check_response=_make_decision(permitted=True))
        with pytest.raises(AssertionError, match="Expected budget to be exceeded"):
            assert_budget_exceeded(engine, category="compute", amount=0.1)


# ---------------------------------------------------------------------------
# TestAssertGovernanceDenied
# ---------------------------------------------------------------------------


class TestAssertGovernanceDenied:
    def test_passes_when_action_is_denied(self) -> None:
        from pytest_governance.assertions import assert_governance_denied

        engine = _make_engine(
            check_sync_responses=[_make_decision(permitted=False)]
        )
        assert_governance_denied(engine, action="file:write")

    def test_fails_when_action_is_permitted(self) -> None:
        from pytest_governance.assertions import assert_governance_denied

        engine = _make_engine(
            check_sync_responses=[_make_decision(permitted=True)]
        )
        with pytest.raises(AssertionError, match="Expected action.*to be denied"):
            assert_governance_denied(engine, action="file:write")


# ---------------------------------------------------------------------------
# TestAssertGovernancePermitted
# ---------------------------------------------------------------------------


class TestAssertGovernancePermitted:
    def test_passes_when_action_is_permitted(self) -> None:
        from pytest_governance.assertions import assert_governance_permitted

        engine = _make_engine(
            check_sync_responses=[_make_decision(permitted=True)]
        )
        assert_governance_permitted(engine, action="file:read")

    def test_fails_when_action_is_denied(self) -> None:
        from pytest_governance.assertions import assert_governance_permitted

        engine = _make_engine(
            check_sync_responses=[_make_decision(permitted=False, reason="Trust too low")]
        )
        with pytest.raises(AssertionError, match="was denied"):
            assert_governance_permitted(engine, action="file:read")


# ---------------------------------------------------------------------------
# TestAssertAuditContains
# ---------------------------------------------------------------------------


class TestAssertAuditContains:
    def test_passes_when_audit_record_exists(self) -> None:
        from pytest_governance.assertions import assert_audit_contains

        mock_record = MagicMock()
        engine = _make_engine(audit_records=[mock_record])
        assert_audit_contains(engine, action="file:write")

    def test_fails_when_no_audit_records(self) -> None:
        from pytest_governance.assertions import assert_audit_contains

        engine = _make_engine(audit_records=[])
        with pytest.raises(AssertionError, match="No audit records found"):
            assert_audit_contains(engine, action="file:write")

    def test_fails_when_count_mismatches(self) -> None:
        from pytest_governance.assertions import assert_audit_contains

        engine = _make_engine(audit_records=[MagicMock(), MagicMock()])
        with pytest.raises(AssertionError, match="Expected exactly 1"):
            assert_audit_contains(engine, action="file:write", count=1)

    def test_passes_with_exact_count(self) -> None:
        from pytest_governance.assertions import assert_audit_contains

        engine = _make_engine(audit_records=[MagicMock(), MagicMock()])
        assert_audit_contains(engine, action="file:write", count=2)
