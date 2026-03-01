# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""
Standalone trust-level and budget assertion helpers.

These helpers are callable directly in test functions without fixtures.
They provide clear, focused assertion messages that make governance test
failures easy to diagnose.

All functions accept the governance engine as their first argument so they
compose naturally as test helper utilities rather than coupled methods.

Example
-------
>>> from pytest_governance.trust_assertions import (
...     assert_trust_level,
...     assert_budget_remaining,
...     assert_consent_granted,
...     assert_audit_contains,
... )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aumos_governance import GovernanceEngine  # type: ignore[import]

__all__ = [
    "assert_trust_level",
    "assert_budget_remaining",
    "assert_consent_granted",
    "assert_audit_contains",
]


def assert_trust_level(
    engine: "GovernanceEngine",
    agent_id: str,
    expected_level: int,
    scope: str = "default",
) -> None:
    """Assert that *agent_id* currently holds exactly *expected_level* trust.

    This is a point-in-time check — it reads the current trust level from the
    engine and compares it to *expected_level* without performing any action.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    agent_id:
        The agent whose trust level is being checked.
    expected_level:
        The trust level the agent is expected to hold.
    scope:
        The trust scope to read from. Defaults to ``"default"``.

    Raises
    ------
    AssertionError:
        If the actual trust level does not equal *expected_level*.
    ValueError:
        If *expected_level* is negative.
    """
    if expected_level < 0:
        raise ValueError(
            f"expected_level must be >= 0, got {expected_level!r}"
        )

    actual_level = engine.trust.get_level(agent_id, scope)
    assert actual_level == expected_level, (
        f"Agent '{agent_id}' (scope='{scope}') should be at trust level L{expected_level} "
        f"but is currently at L{actual_level}. "
        f"Trust levels are set manually — check that the setup code "
        f"called engine.trust.set_level('{agent_id}', {expected_level}, '{scope}')."
    )


def assert_budget_remaining(
    engine: "GovernanceEngine",
    agent_id: str,
    min_remaining: float,
    category: str = "default",
) -> None:
    """Assert that *agent_id* has at least *min_remaining* budget left.

    Reads the current budget balance from the engine and verifies it is
    greater than or equal to *min_remaining*.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    agent_id:
        The agent whose budget is being checked.
    min_remaining:
        The minimum budget balance required.
    category:
        The budget category (envelope) to check. Defaults to ``"default"``.

    Raises
    ------
    AssertionError:
        If the remaining budget is below *min_remaining*.
    ValueError:
        If *min_remaining* is negative.
    """
    if min_remaining < 0:
        raise ValueError(
            f"min_remaining must be >= 0, got {min_remaining!r}"
        )

    remaining = engine.budget.get_remaining(agent_id, category)
    assert remaining >= min_remaining, (
        f"Agent '{agent_id}' (category='{category}') should have at least "
        f"{min_remaining} budget remaining, but only has {remaining}. "
        f"Check that budget was not over-consumed by earlier test operations."
    )


def assert_consent_granted(
    engine: "GovernanceEngine",
    agent_id: str,
    resource: str,
) -> None:
    """Assert that consent has been explicitly granted for *agent_id* to access *resource*.

    Verifies that the consent layer returns a granted status for the
    (agent_id, resource) pair. This checks the consent state directly —
    it does not invoke a governance check or simulate an action.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    agent_id:
        The agent whose consent status is being checked.
    resource:
        The resource identifier for which consent is expected.

    Raises
    ------
    AssertionError:
        If consent has NOT been granted for the (agent_id, resource) pair.
    """
    is_granted = engine.consent.is_granted(agent_id, resource)
    assert is_granted, (
        f"Expected consent to be granted for agent '{agent_id}' on resource '{resource}', "
        f"but consent was not found. "
        f"Call engine.consent.grant('{agent_id}', '{resource}') in the test setup, "
        f"or verify that the consent grant did not expire."
    )


def assert_audit_contains(
    engine: "GovernanceEngine",
    agent_id: str,
    action_type: str,
    min_count: int = 1,
) -> None:
    """Assert the audit log contains at least *min_count* entries of *action_type* for *agent_id*.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance.
    agent_id:
        The agent whose audit log is being inspected.
    action_type:
        The action string to search for (e.g. ``"tool_call"``, ``"file:write"``).
    min_count:
        The minimum number of audit records expected. Defaults to 1.

    Raises
    ------
    AssertionError:
        If fewer than *min_count* records are found.
    ValueError:
        If *min_count* is less than 1.
    """
    if min_count < 1:
        raise ValueError(
            f"min_count must be >= 1, got {min_count!r}"
        )

    records = engine.audit.query(agent_id=agent_id, action=action_type)
    assert len(records) >= min_count, (
        f"Expected at least {min_count} audit record(s) for agent '{agent_id}' "
        f"with action_type='{action_type}', but found {len(records)}. "
        f"Ensure that the action was executed and that audit logging is enabled "
        f"in the test's GovernanceEngine configuration."
    )
