# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""pytest plugin for AumOS governance testing.

Auto-registered via the ``pytest11`` entry-point in pyproject.toml.

Usage:
    pytest --governance        # activates governance marker reporting
    pytest -m governance       # run only governance-marked tests

Fixtures provided here are available in all test modules once the plugin
is installed — no import required in conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator

import pytest

if TYPE_CHECKING:
    from aumos_governance import BudgetManager, GovernanceEngine, TrustManager


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --governance CLI flag."""
    group = parser.getgroup("governance", "AumOS Governance testing options")
    group.addoption(
        "--governance",
        action="store_true",
        default=False,
        help="Enable AumOS governance testing fixtures and enhanced marker reporting.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the 'governance' marker so it appears in --markers output."""
    config.addinivalue_line(
        "markers",
        "governance: mark test as an AumOS governance correctness test",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """When --governance is active, add a visual marker to governance tests."""
    if not config.getoption("--governance", default=False):
        return
    governance_marker = pytest.mark.governance
    for item in items:
        if "governance" in item.keywords:
            # Already marked — just ensure the mark is registered
            continue
        # Automatically mark any test that uses governance fixtures
        fixture_names: tuple[str, ...] = getattr(item, "fixturenames", ())
        governance_fixtures = {
            "governance_engine",
            "trust_manager",
            "budget_manager",
            "governed_agent",
            "budget_envelope",
        }
        if governance_fixtures.intersection(fixture_names):
            item.add_marker(governance_marker)


@pytest.fixture
def governance_engine() -> Generator["GovernanceEngine", None, None]:
    """Provide a fresh GovernanceEngine configured for test use.

    Yields a real engine instance — not a mock — so tests exercise actual
    governance logic. The engine is torn down after each test function.

    Example::

        def test_write_requires_trust(governance_engine):
            from pytest_governance.assertions import assert_trust_required
            assert_trust_required(governance_engine, action="file:write", required_level=3)
    """
    from aumos_governance import GovernanceConfig, GovernanceEngine  # type: ignore[import]

    config = GovernanceConfig.default()
    engine = GovernanceEngine(config)
    yield engine
    # Teardown: release any resources held by the engine (e.g. in-memory audit store)
    if hasattr(engine, "close"):
        engine.close()


@pytest.fixture
def trust_manager(governance_engine: "GovernanceEngine") -> "TrustManager":
    """Provide the TrustManager from a fresh GovernanceEngine.

    Shortcut for ``governance_engine.trust`` when only trust operations are needed.

    Example::

        def test_level_propagation(trust_manager):
            trust_manager.set_level("agent-a", 3, "default")
            assert trust_manager.get_level("agent-a", "default") == 3
    """
    return governance_engine.trust  # type: ignore[return-value]


@pytest.fixture
def budget_manager(governance_engine: "GovernanceEngine") -> "BudgetManager":
    """Provide the BudgetManager from a fresh GovernanceEngine.

    Shortcut for ``governance_engine.budget`` when only budget operations are needed.

    Example::

        def test_budget_depletion(budget_manager):
            budget_manager.create_envelope("llm", limit=10.0, period_seconds=3600)
            budget_manager.consume("llm", 10.0)
            result = budget_manager.check("llm", 0.01)
            assert not result.permitted
    """
    return governance_engine.budget  # type: ignore[return-value]
