# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""Fluent matchers for AumOS governance decisions.

Provides ``GovernanceDecisionMatcher`` — a chainable assertion object — and
the ``expect_decision()`` factory function as its public entry-point.

Usage::

    from pytest_governance.matchers import expect_decision

    def test_detailed_denial(governance_engine):
        decision = governance_engine.check_sync(
            action="file:delete",
            context={"agent_id": "low-trust"},
        )
        (
            expect_decision(decision)
            .is_denied()
            .with_reason("trust")
            .at_trust_level(1)
        )

All matcher methods return ``self`` to enable chaining. Each call that fails
raises an ``AssertionError`` with a descriptive message; pytest will display
these as normal test failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # GovernanceDecision is duck-typed via Any to avoid hard runtime dependency


class GovernanceDecisionMatcher:
    """Fluent assertion wrapper for a ``GovernanceDecision`` object.

    Instantiate via :func:`expect_decision` rather than directly.
    """

    def __init__(self, decision: Any) -> None:
        self._decision = decision

    # ------------------------------------------------------------------
    # Top-level permit / deny
    # ------------------------------------------------------------------

    def is_permitted(self) -> "GovernanceDecisionMatcher":
        """Assert that the decision is permitted.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If ``decision.permitted`` is ``False``.
        """
        assert self._decision.permitted, (
            f"Expected governance decision to be permitted, "
            f"but it was denied. Reason: {self._decision.reason}"
        )
        return self

    def is_denied(self) -> "GovernanceDecisionMatcher":
        """Assert that the decision is denied.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If ``decision.permitted`` is ``True``.
        """
        assert not self._decision.permitted, (
            "Expected governance decision to be denied, but it was permitted."
        )
        return self

    # ------------------------------------------------------------------
    # Reason matching
    # ------------------------------------------------------------------

    def with_reason(self, reason: str) -> "GovernanceDecisionMatcher":
        """Assert that the denial reason contains ``reason`` as a substring.

        Parameters
        ----------
        reason:
            Substring expected to appear in ``decision.reason``.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If the reason string does not contain ``reason``.
        """
        actual_reason: str = getattr(self._decision, "reason", "") or ""
        assert reason in actual_reason, (
            f"Expected governance decision reason to contain '{reason}', "
            f"but got: '{actual_reason}'"
        )
        return self

    def without_reason(self, reason: str) -> "GovernanceDecisionMatcher":
        """Assert that the denial reason does NOT contain ``reason``.

        Parameters
        ----------
        reason:
            Substring that must NOT appear in ``decision.reason``.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If the reason string unexpectedly contains ``reason``.
        """
        actual_reason: str = getattr(self._decision, "reason", "") or ""
        assert reason not in actual_reason, (
            f"Expected governance decision reason NOT to contain '{reason}', "
            f"but it does. Full reason: '{actual_reason}'"
        )
        return self

    # ------------------------------------------------------------------
    # Trust sub-decision
    # ------------------------------------------------------------------

    def at_trust_level(self, level: int) -> "GovernanceDecisionMatcher":
        """Assert that the agent's current trust level in the decision equals ``level``.

        Parameters
        ----------
        level:
            The expected current trust level.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If ``decision.trust.current_level`` does not equal ``level``.
        AttributeError:
            If the decision does not include a ``trust`` sub-object.
        """
        trust_sub = self._decision.trust
        actual_level: int = trust_sub.current_level
        assert actual_level == level, (
            f"Expected current trust level {level}, but got {actual_level}."
        )
        return self

    def requires_trust_level(self, level: int) -> "GovernanceDecisionMatcher":
        """Assert that the action's required trust level in the decision equals ``level``.

        Parameters
        ----------
        level:
            The expected required trust level from the policy.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If ``decision.trust.required_level`` does not equal ``level``.
        """
        trust_sub = self._decision.trust
        actual_required: int = trust_sub.required_level
        assert actual_required == level, (
            f"Expected required trust level {level}, but policy specifies {actual_required}."
        )
        return self

    # ------------------------------------------------------------------
    # Budget sub-decision
    # ------------------------------------------------------------------

    def with_budget_available(self, minimum: float) -> "GovernanceDecisionMatcher":
        """Assert that the available budget in the decision is >= ``minimum``.

        Parameters
        ----------
        minimum:
            The minimum expected available budget amount.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If the available budget is below ``minimum``.
        """
        budget_sub = getattr(self._decision, "budget", None)
        available: float = getattr(budget_sub, "available", 0.0) if budget_sub else 0.0
        assert available >= minimum, (
            f"Expected available budget >= {minimum}, but got {available}."
        )
        return self

    # ------------------------------------------------------------------
    # Consent sub-decision
    # ------------------------------------------------------------------

    def with_consent_granted(self) -> "GovernanceDecisionMatcher":
        """Assert that the consent sub-decision is permitted.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If consent was not granted or the consent sub-object is absent.
        """
        consent_sub = getattr(self._decision, "consent", None)
        assert consent_sub is not None, (
            "Expected a consent sub-decision, but 'decision.consent' is absent."
        )
        assert consent_sub.permitted, (
            f"Expected consent to be granted, but it was denied. "
            f"Reason: {getattr(consent_sub, 'reason', 'unknown')}"
        )
        return self

    def with_consent_denied(self) -> "GovernanceDecisionMatcher":
        """Assert that the consent sub-decision is denied.

        Returns
        -------
        GovernanceDecisionMatcher
            ``self``, to allow further chaining.

        Raises
        ------
        AssertionError:
            If consent was granted or the consent sub-object is absent.
        """
        consent_sub = getattr(self._decision, "consent", None)
        assert consent_sub is not None, (
            "Expected a consent sub-decision, but 'decision.consent' is absent."
        )
        assert not consent_sub.permitted, (
            "Expected consent to be denied, but it was granted."
        )
        return self


def expect_decision(decision: Any) -> GovernanceDecisionMatcher:
    """Wrap a ``GovernanceDecision`` in a fluent matcher.

    This is the preferred entry-point for ``GovernanceDecisionMatcher``.

    Parameters
    ----------
    decision:
        A ``GovernanceDecision`` object returned by ``engine.check_sync()``.

    Returns
    -------
    GovernanceDecisionMatcher
        A fluent matcher wrapping the decision.

    Example::

        expect_decision(decision).is_denied().with_reason("budget")
    """
    return GovernanceDecisionMatcher(decision)
