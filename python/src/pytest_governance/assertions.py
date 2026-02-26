# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""Governance-specific assertion helpers for pytest.

All functions in this module are standalone — they can be imported and called
directly in test functions without using fixtures:

    from pytest_governance.assertions import assert_trust_required

    def test_write_requires_l3(governance_engine):
        assert_trust_required(governance_engine, action="file:write", required_level=3)

Design notes
------------
- Assertions always produce clear failure messages that include the action name,
  expected level, and actual decision outcome.
- ``assert_trust_required`` tests BOTH sides of the trust boundary in a single
  call to guard against both false positives and false negatives.
- Functions accept ``engine`` as their first positional argument so they compose
  naturally as helpers rather than methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aumos_governance import GovernanceEngine  # type: ignore[import]


def assert_trust_required(
    engine: "GovernanceEngine",
    action: str,
    required_level: int,
    agent_id: str = "test-agent",
    scope: str = "default",
) -> None:
    """Assert that ``action`` requires exactly ``required_level`` trust.

    This performs a two-sided boundary check:

    1. Sets the agent to ``required_level - 1`` and asserts the action is **denied**.
    2. Sets the agent to ``required_level`` and asserts the action is **permitted**.

    Both checks must pass for the assertion to succeed. This prevents tests from
    passing when a policy is too permissive (allows below the required level) or
    too restrictive (blocks at the required level).

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance (typically from the ``governance_engine`` fixture).
    action:
        The action string to check, e.g. ``"file:write"``.
    required_level:
        The minimum trust level the action should require. Must be >= 1.
    agent_id:
        The agent identifier to use for the test. Defaults to ``"test-agent"``.
    scope:
        The trust scope to apply the level within. Defaults to ``"default"``.

    Raises
    ------
    AssertionError:
        If the action is permitted below the required level, or denied at the
        required level.
    ValueError:
        If ``required_level`` is less than 1 (there is no level 0 boundary to test).
    """
    if required_level < 1:
        raise ValueError(
            f"required_level must be >= 1 to test a meaningful boundary, got {required_level}"
        )

    # --- Side 1: one level below required → must be denied ---
    engine.trust.set_level(agent_id, required_level - 1, scope)
    below_decision = engine.check_sync(
        action=action,
        context={"agent_id": agent_id, "scope": scope},
    )
    assert not below_decision.permitted, (
        f"Action '{action}' should require trust level L{required_level} "
        f"but was permitted at L{required_level - 1}. "
        f"Check that the policy for '{action}' enforces the minimum correctly."
    )

    # --- Side 2: at required level → must be permitted ---
    engine.trust.set_level(agent_id, required_level, scope)
    at_decision = engine.check_sync(
        action=action,
        context={"agent_id": agent_id, "scope": scope},
    )
    assert at_decision.permitted, (
        f"Action '{action}' should be permitted at trust level L{required_level} "
        f"but was denied. Denial reason: {at_decision.reason}"
    )


def assert_budget_sufficient(
    engine: "GovernanceEngine",
    category: str,
    amount: float,
) -> None:
    """Assert that a budget check passes for the given ``amount`` in ``category``.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    category:
        The budget category (envelope) name to check.
    amount:
        The amount to check against the budget.

    Raises
    ------
    AssertionError:
        If the budget check fails (insufficient funds).
    """
    result = engine.budget.check(category, amount)
    assert result.permitted, (
        f"Budget check failed for category '{category}', amount {amount}. "
        f"Reason: {result.reason}. "
        f"Available: {getattr(result, 'available', 'unknown')}"
    )


def assert_budget_exceeded(
    engine: "GovernanceEngine",
    category: str,
    amount: float,
) -> None:
    """Assert that a budget check fails for the given ``amount`` in ``category``.

    Use this to verify that a budget limit is enforced — the check for ``amount``
    must be denied.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    category:
        The budget category (envelope) name to check.
    amount:
        The amount that should exceed the available budget.

    Raises
    ------
    AssertionError:
        If the budget check unexpectedly passes (budget not exceeded).
    """
    result = engine.budget.check(category, amount)
    assert not result.permitted, (
        f"Expected budget to be exceeded for category '{category}', amount {amount}, "
        f"but the check was permitted. "
        f"Available: {getattr(result, 'available', 'unknown')}"
    )


def assert_consent_required(
    engine: "GovernanceEngine",
    action: str,
    agent_id: str = "test-agent",
) -> None:
    """Assert that ``action`` requires consent.

    Checks that the governance decision is either fully denied or that the
    consent sub-decision is not permitted, confirming that the action cannot
    proceed without explicit consent being granted.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    action:
        The action string to check, e.g. ``"pii:read"``.
    agent_id:
        The agent identifier to use for the test. Defaults to ``"test-agent"``.

    Raises
    ------
    AssertionError:
        If the action is permitted without consent.
    """
    decision = engine.check_sync(
        action=action,
        context={"agent_id": agent_id},
    )
    consent_sub = getattr(decision, "consent", None)
    consent_denied = consent_sub is not None and not consent_sub.permitted

    assert not decision.permitted or consent_denied, (
        f"Action '{action}' should require consent for agent '{agent_id}' "
        f"but was fully permitted without it. "
        f"Ensure the policy for '{action}' includes a consent requirement."
    )


def assert_governance_denied(
    engine: "GovernanceEngine",
    action: str,
    agent_id: str = "test-agent",
    context: dict[str, object] | None = None,
) -> None:
    """Assert that ``action`` is denied by the governance engine.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    action:
        The action string to check.
    agent_id:
        The agent identifier to use for the test. Defaults to ``"test-agent"``.
    context:
        Optional additional context to merge into the check call.

    Raises
    ------
    AssertionError:
        If the action is unexpectedly permitted.
    """
    check_context: dict[str, object] = {"agent_id": agent_id}
    if context:
        check_context.update(context)

    decision = engine.check_sync(action=action, context=check_context)
    assert not decision.permitted, (
        f"Expected action '{action}' to be denied for agent '{agent_id}' "
        f"but it was permitted."
    )


def assert_governance_permitted(
    engine: "GovernanceEngine",
    action: str,
    agent_id: str = "test-agent",
    context: dict[str, object] | None = None,
) -> None:
    """Assert that ``action`` is permitted by the governance engine.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    action:
        The action string to check.
    agent_id:
        The agent identifier to use for the test. Defaults to ``"test-agent"``.
    context:
        Optional additional context to merge into the check call.

    Raises
    ------
    AssertionError:
        If the action is denied.
    """
    check_context: dict[str, object] = {"agent_id": agent_id}
    if context:
        check_context.update(context)

    decision = engine.check_sync(action=action, context=check_context)
    assert decision.permitted, (
        f"Expected action '{action}' to be permitted for agent '{agent_id}' "
        f"but was denied. Reason: {decision.reason}"
    )


def assert_audit_contains(
    engine: "GovernanceEngine",
    action: str,
    count: int | None = None,
) -> None:
    """Assert that the audit log contains at least one entry for ``action``.

    Optionally assert that the number of entries equals ``count``.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    action:
        The action string to search for in the audit log.
    count:
        If provided, the exact number of audit records expected. If ``None``,
        only the presence of at least one record is asserted.

    Raises
    ------
    AssertionError:
        If no audit records are found, or if the record count does not match
        the expected ``count``.
    """
    records = engine.audit.query(action=action)
    assert len(records) > 0, (
        f"No audit records found for action '{action}'. "
        f"Ensure the action was executed and audit logging is enabled."
    )
    if count is not None:
        assert len(records) == count, (
            f"Expected exactly {count} audit record(s) for action '{action}', "
            f"but found {len(records)}."
        )
