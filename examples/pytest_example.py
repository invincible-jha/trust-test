# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""pytest example for pytest-aumos-governance.

This file demonstrates how to use the pytest-aumos-governance fixtures,
standalone assertion helpers, and the fluent GovernanceDecisionMatcher to
write governance-correctness tests.

Run this file with:

    pytest trust-test/examples/pytest_example.py -v

The governance_engine fixture is automatically registered by the
pytest-aumos-governance plugin when it is installed. The engine is configured
with test-safe defaults and is reset between tests.
"""

from __future__ import annotations

import pytest

from pytest_governance import (
    GovernanceDecisionMatcher,
    assert_audit_contains,
    assert_budget_exceeded,
    assert_budget_sufficient,
    assert_governance_denied,
    assert_governance_permitted,
    assert_trust_required,
    expect_decision,
)


# ---------------------------------------------------------------------------
# Fixture setup
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine_with_budget(governance_engine):  # type: ignore[no-untyped-def]
    """Extend the base governance_engine fixture with a pre-configured budget.

    The base fixture is provided automatically by the pytest-aumos-governance
    plugin. This fixture simply adds a budget envelope for common tests.
    """
    governance_engine.budget.create_envelope("llm", limit=10.0)
    governance_engine.budget.create_envelope("network", limit=5.0)
    return governance_engine


# ---------------------------------------------------------------------------
# Trust level tests
# ---------------------------------------------------------------------------


class TestTrustPolicies:
    """Tests that verify governance actions are tied to the correct trust level."""

    def test_file_read_requires_level_2(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """file:read should require trust level 2 — not permitted at L1, permitted at L2."""
        assert_trust_required(
            governance_engine,
            action="file:read",
            required_level=2,
            agent_id="reader-agent",
        )

    def test_file_write_requires_level_3(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """file:write should require trust level 3 — more sensitive than read."""
        assert_trust_required(
            governance_engine,
            action="file:write",
            required_level=3,
            agent_id="writer-agent",
        )

    def test_low_trust_agent_denied(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """An agent at trust level 0 should be denied all sensitive actions."""
        governance_engine.trust.set_level("untrusted", 0)
        assert_governance_denied(
            governance_engine,
            action="file:write",
            agent_id="untrusted",
        )

    def test_high_trust_agent_permitted(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """An agent at trust level 4 should be permitted standard operations."""
        governance_engine.trust.set_level("privileged", 4)
        assert_governance_permitted(
            governance_engine,
            action="file:read",
            agent_id="privileged",
        )


# ---------------------------------------------------------------------------
# Budget tests
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    """Tests that verify budget limits are correctly enforced."""

    def test_budget_check_passes_within_limit(self, engine_with_budget) -> None:  # type: ignore[no-untyped-def]
        """A spend of 3.0 against a 10.0 LLM budget should succeed."""
        assert_budget_sufficient(engine_with_budget, category="llm", amount=3.0)

    def test_budget_check_fails_over_limit(self, engine_with_budget) -> None:  # type: ignore[no-untyped-def]
        """A spend of 15.0 against a 10.0 LLM budget should be denied."""
        assert_budget_exceeded(engine_with_budget, category="llm", amount=15.0)

    def test_budget_exact_limit_permitted(self, engine_with_budget) -> None:  # type: ignore[no-untyped-def]
        """A spend equal to the budget limit should be permitted (inclusive boundary)."""
        assert_budget_sufficient(engine_with_budget, category="llm", amount=10.0)

    def test_budget_one_over_limit_denied(self, engine_with_budget) -> None:  # type: ignore[no-untyped-def]
        """A spend of limit+0.01 should be denied."""
        assert_budget_exceeded(engine_with_budget, category="network", amount=5.01)


# ---------------------------------------------------------------------------
# Fluent matcher tests
# ---------------------------------------------------------------------------


class TestFluentMatchers:
    """Tests that demonstrate the GovernanceDecisionMatcher fluent API."""

    def test_denial_with_reason_chain(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """Chain is_denied() and with_reason() to assert both the outcome and its cause."""
        governance_engine.trust.set_level("low-trust", 1)

        decision = governance_engine.check_sync(
            action="file:write",
            context={"agent_id": "low-trust"},
        )

        (
            expect_decision(decision)
            .is_denied()
            .with_reason("trust")
        )

    def test_permitted_with_budget_available(  # type: ignore[no-untyped-def]
        self, engine_with_budget
    ) -> None:
        """Verify that a permitted action reports budget availability."""
        engine_with_budget.trust.set_level("agent-a", 3)

        decision = engine_with_budget.check_sync(
            action="file:write",
            context={"agent_id": "agent-a"},
        )

        (
            expect_decision(decision)
            .is_permitted()
            .with_budget_available(1.0)
        )

    def test_trust_level_in_decision(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """The decision's trust sub-object should reflect the agent's current level."""
        governance_engine.trust.set_level("checker", 2)

        decision = governance_engine.check_sync(
            action="file:read",
            context={"agent_id": "checker"},
        )

        (
            expect_decision(decision)
            .at_trust_level(2)
            .requires_trust_level(2)
        )

    def test_denial_without_unexpected_reason(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """A trust denial should not cite a budget reason."""
        governance_engine.trust.set_level("agent-b", 0)

        decision = governance_engine.check_sync(
            action="file:read",
            context={"agent_id": "agent-b"},
        )

        (
            expect_decision(decision)
            .is_denied()
            .with_reason("trust")
            .without_reason("budget")
        )


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------


class TestAuditLog:
    """Tests that verify governance decisions are recorded in the audit log."""

    def test_audit_records_denied_action(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """Denied actions must appear in the audit log."""
        governance_engine.trust.set_level("audited", 0)

        governance_engine.check_sync(
            action="file:write",
            context={"agent_id": "audited"},
        )

        assert_audit_contains(governance_engine, action="file:write")

    def test_audit_count_matches_invocations(self, governance_engine) -> None:  # type: ignore[no-untyped-def]
        """Running the same action twice should produce two audit records."""
        governance_engine.trust.set_level("counter-agent", 2)

        for _ in range(2):
            governance_engine.check_sync(
                action="file:read",
                context={"agent_id": "counter-agent"},
            )

        assert_audit_contains(
            governance_engine,
            action="file:read",
            count=2,
        )
