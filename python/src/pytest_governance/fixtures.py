# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""Factory fixtures for AumOS governance testing.

These fixtures return callable factories rather than fixed objects, letting
individual test functions customise their setup with inline parameters while
still sharing the same underlying ``GovernanceEngine`` from the session.

Usage example::

    def test_high_trust_agent_permitted(governance_engine, governed_agent):
        governed_agent(agent_id="high-trust", trust_level=4)
        from pytest_governance.assertions import assert_governance_permitted
        assert_governance_permitted(governance_engine, "admin:reset", agent_id="high-trust")

    def test_llm_budget_capped(governance_engine, budget_envelope):
        budget_envelope(category="llm", limit=5.0)
        from pytest_governance.assertions import assert_budget_exceeded
        assert_budget_exceeded(governance_engine, "llm", amount=10.0)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pytest

if TYPE_CHECKING:
    from aumos_governance import GovernanceEngine  # type: ignore[import]


@pytest.fixture
def governed_agent(
    governance_engine: "GovernanceEngine",
) -> Callable[[str, int, str], str]:
    """Factory fixture: create a test agent with a configurable trust level.

    Returns a callable with the signature::

        governed_agent(
            agent_id: str = "test-agent",
            trust_level: int = 2,
            scope: str = "default",
        ) -> str

    The callable registers the agent in the engine's trust store and returns
    ``agent_id`` so callers can chain it directly into assertions.

    Example::

        def test_mid_trust(governance_engine, governed_agent):
            agent = governed_agent(agent_id="mid", trust_level=2)
            assert_governance_permitted(governance_engine, "file:read", agent_id=agent)
    """

    def _make(
        agent_id: str = "test-agent",
        trust_level: int = 2,
        scope: str = "default",
    ) -> str:
        governance_engine.trust.set_level(agent_id, trust_level, scope)
        return agent_id

    return _make


@pytest.fixture
def budget_envelope(
    governance_engine: "GovernanceEngine",
) -> Callable[[str, float, int], str]:
    """Factory fixture: create a test budget envelope.

    Returns a callable with the signature::

        budget_envelope(
            category: str = "test",
            limit: float = 100.0,
            period_seconds: int = 3600,
        ) -> str

    The callable registers a budget envelope in the engine's budget manager
    and returns ``category`` so callers can chain it directly into assertions.

    Example::

        def test_budget_limit(governance_engine, budget_envelope):
            envelope = budget_envelope(category="llm", limit=10.0)
            assert_budget_sufficient(governance_engine, envelope, amount=5.0)
            assert_budget_exceeded(governance_engine, envelope, amount=15.0)
    """

    def _make(
        category: str = "test",
        limit: float = 100.0,
        period_seconds: int = 3600,
    ) -> str:
        governance_engine.budget.create_envelope(category, limit, period_seconds)
        return category

    return _make
