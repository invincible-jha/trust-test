# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""
Pre-built benchmark scenarios for common governance patterns.

Provides a ``BenchmarkSuite`` containing self-contained scenario functions that
can be used to validate that a ``GovernanceEngine`` implementation correctly
handles the four fundamental governance patterns:

1. ``basic_trust``          — action permissions at different trust levels
2. ``budget_depletion``     — budget enforcement as spending accumulates
3. ``consent_revocation``   — consent state changes propagate to decisions
4. ``audit_integrity``      — all decisions are recorded in the audit log

Run all benchmarks with ``run_benchmarks(engine)`` or run individual scenarios
via ``BenchmarkSuite.run_scenario(engine, scenario_name)``.

Example
-------
>>> from pytest_governance.benchmarks import BenchmarkSuite, run_benchmarks
>>> suite = BenchmarkSuite()
>>> report = run_benchmarks(engine)
>>> print(report.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from aumos_governance import GovernanceEngine  # type: ignore[import]

__all__ = ["BenchmarkScenario", "BenchmarkResult", "BenchmarkReport", "BenchmarkSuite", "run_benchmarks"]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkScenario:
    """Metadata about a registered benchmark scenario.

    Attributes:
        name:        Unique scenario identifier.
        description: Human-readable summary of what the scenario tests.
        tags:        Optional list of tag strings for filtering.
    """

    name: str
    description: str
    tags: list[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """The outcome of running one benchmark scenario.

    Attributes:
        scenario_name:     Name of the scenario that was run.
        passed:            True if all assertions in the scenario passed.
        duration_seconds:  Wall clock time to run the scenario.
        error_message:     Failure detail when ``passed=False``.
    """

    scenario_name: str
    passed: bool
    duration_seconds: float
    error_message: str = ""


@dataclass
class BenchmarkReport:
    """Aggregate results from running the full benchmark suite.

    Attributes:
        results: List of ``BenchmarkResult`` instances.
    """

    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of scenarios run."""
        return len(self.results)

    @property
    def passed_count(self) -> int:
        """Number of scenarios that passed."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        """Number of scenarios that failed."""
        return sum(1 for r in self.results if not r.passed)

    @property
    def total_duration(self) -> float:
        """Total wall clock time across all scenarios."""
        return sum(r.duration_seconds for r in self.results)

    def summary(self) -> str:
        """Return a human-readable summary of the benchmark run."""
        lines = [
            "",
            "AumOS Governance Benchmark Suite",
            "=" * 50,
        ]
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(
                f"  [{status}] {result.scenario_name:<35} "
                f"({result.duration_seconds:.3f}s)"
            )
            if not result.passed and result.error_message:
                lines.append(f"         {result.error_message}")

        lines += [
            "-" * 50,
            f"  Total: {self.total} | Passed: {self.passed_count} | "
            f"Failed: {self.failed_count} | "
            f"Duration: {self.total_duration:.3f}s",
            "",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario implementations
# ---------------------------------------------------------------------------


def _scenario_basic_trust(engine: "GovernanceEngine") -> None:
    """Verify that low-trust agents are denied and high-trust agents are permitted.

    Sets up two agents at different trust levels and verifies that a
    representative action enforces the minimum trust boundary.
    """
    # Low trust agent — should be denied
    engine.trust.set_level("benchmark-low-trust", 1, "default")
    low_decision = engine.check_sync(
        action="file:write",
        context={"agent_id": "benchmark-low-trust", "scope": "default"},
    )
    assert not low_decision.permitted, (
        "Expected 'file:write' to be denied at trust level L1, "
        f"but it was permitted. Decision reason: {low_decision.reason}"
    )

    # High trust agent — should be permitted
    engine.trust.set_level("benchmark-high-trust", 4, "default")
    high_decision = engine.check_sync(
        action="file:write",
        context={"agent_id": "benchmark-high-trust", "scope": "default"},
    )
    assert high_decision.permitted, (
        "Expected 'file:write' to be permitted at trust level L4, "
        f"but it was denied. Decision reason: {high_decision.reason}"
    )


def _scenario_budget_depletion(engine: "GovernanceEngine") -> None:
    """Verify that budget limits are enforced as spending accumulates.

    Allocates a budget, spends most of it, then asserts that the remaining
    amount is tracked correctly and that an over-budget request is denied.
    """
    agent_id = "benchmark-budget-agent"

    # Set initial budget
    engine.budget.set_limit(agent_id, category="api", limit=1.00)

    # First check within budget — should succeed
    within_budget = engine.budget.check(agent_id, category="api", amount=0.50)
    assert within_budget.permitted, (
        f"Budget check for 0.50 of 1.00 should be permitted. "
        f"Reason: {within_budget.reason}"
    )

    # Record the spend
    engine.budget.deduct(agent_id, category="api", amount=0.50)

    # Second check that would exceed remaining budget — should fail
    over_budget = engine.budget.check(agent_id, category="api", amount=0.75)
    assert not over_budget.permitted, (
        "Budget check for 0.75 after 0.50 already spent (of 1.00 limit) "
        "should be denied, but was permitted."
    )


def _scenario_consent_revocation(engine: "GovernanceEngine") -> None:
    """Verify that revoking consent immediately prevents further access.

    Grants consent, verifies the action is permitted, revokes consent, and
    verifies the same action is now denied.
    """
    agent_id = "benchmark-consent-agent"
    resource = "user:profile:benchmark"

    # Grant consent and verify action is permitted
    engine.consent.grant(agent_id, resource)
    granted_decision = engine.check_sync(
        action="pii:read",
        context={"agent_id": agent_id, "resource": resource},
    )
    assert granted_decision.permitted, (
        f"Action 'pii:read' should be permitted after consent is granted. "
        f"Decision reason: {granted_decision.reason}"
    )

    # Revoke consent and verify action is now denied
    engine.consent.revoke(agent_id, resource)
    revoked_decision = engine.check_sync(
        action="pii:read",
        context={"agent_id": agent_id, "resource": resource},
    )
    assert not revoked_decision.permitted, (
        f"Action 'pii:read' should be denied after consent is revoked. "
        f"Decision reason: {revoked_decision.reason}"
    )


def _scenario_audit_integrity(engine: "GovernanceEngine") -> None:
    """Verify that all governance decisions are recorded in the audit log.

    Performs two decisions and verifies that both appear in the audit trail.
    """
    agent_id = "benchmark-audit-agent"
    engine.trust.set_level(agent_id, 3, "default")

    engine.check_sync(
        action="tool:read",
        context={"agent_id": agent_id},
    )
    engine.check_sync(
        action="tool:write",
        context={"agent_id": agent_id},
    )

    read_records = engine.audit.query(agent_id=agent_id, action="tool:read")
    write_records = engine.audit.query(agent_id=agent_id, action="tool:write")

    assert len(read_records) >= 1, (
        f"Expected at least 1 audit record for 'tool:read' by '{agent_id}', "
        f"but found {len(read_records)}."
    )
    assert len(write_records) >= 1, (
        f"Expected at least 1 audit record for 'tool:write' by '{agent_id}', "
        f"but found {len(write_records)}."
    )


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

_SCENARIO_REGISTRY: list[tuple[BenchmarkScenario, Callable[["GovernanceEngine"], None]]] = [
    (
        BenchmarkScenario(
            name="basic_trust",
            description="Verify action permissions enforce trust level boundaries.",
            tags=["trust"],
        ),
        _scenario_basic_trust,
    ),
    (
        BenchmarkScenario(
            name="budget_depletion",
            description="Verify budget limits are enforced as spending accumulates.",
            tags=["budget"],
        ),
        _scenario_budget_depletion,
    ),
    (
        BenchmarkScenario(
            name="consent_revocation",
            description="Verify that revoking consent immediately blocks access.",
            tags=["consent"],
        ),
        _scenario_consent_revocation,
    ),
    (
        BenchmarkScenario(
            name="audit_integrity",
            description="Verify that all governance decisions are recorded in the audit log.",
            tags=["audit"],
        ),
        _scenario_audit_integrity,
    ),
]


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class BenchmarkSuite:
    """Pre-built governance benchmark suite.

    Provides a collection of standard scenarios that test the four core
    governance primitives: trust, budget, consent, and audit.

    Example
    -------
    >>> suite = BenchmarkSuite()
    >>> report = suite.run_all(engine)
    >>> print(report.summary())
    """

    def __init__(self) -> None:
        self._registry = list(_SCENARIO_REGISTRY)

    @property
    def scenarios(self) -> list[BenchmarkScenario]:
        """List of all registered scenarios."""
        return [meta for meta, _ in self._registry]

    def run_scenario(
        self,
        engine: "GovernanceEngine",
        scenario_name: str,
    ) -> BenchmarkResult:
        """Run a single scenario by name.

        Parameters
        ----------
        engine:
            A ``GovernanceEngine`` instance to test against.
        scenario_name:
            The name of the scenario to run.

        Returns
        -------
        BenchmarkResult:
            The outcome of the scenario.

        Raises
        ------
        ValueError:
            If *scenario_name* is not registered.
        """
        for meta, fn in self._registry:
            if meta.name == scenario_name:
                return self._run(meta, fn, engine)

        registered = [m.name for m, _ in self._registry]
        raise ValueError(
            f"Unknown benchmark scenario: '{scenario_name}'. "
            f"Registered scenarios: {registered}"
        )

    def run_all(self, engine: "GovernanceEngine") -> BenchmarkReport:
        """Run all registered scenarios and return an aggregate report.

        Parameters
        ----------
        engine:
            A ``GovernanceEngine`` instance to test against.

        Returns
        -------
        BenchmarkReport:
            Aggregate results across all scenarios.
        """
        results: list[BenchmarkResult] = []
        for meta, fn in self._registry:
            results.append(self._run(meta, fn, engine))
        return BenchmarkReport(results=results)

    @staticmethod
    def _run(
        meta: BenchmarkScenario,
        fn: Callable[["GovernanceEngine"], None],
        engine: "GovernanceEngine",
    ) -> BenchmarkResult:
        """Execute a single scenario function and capture the result."""
        start = time.monotonic()
        try:
            fn(engine)
            duration = time.monotonic() - start
            return BenchmarkResult(
                scenario_name=meta.name,
                passed=True,
                duration_seconds=duration,
            )
        except AssertionError as exc:
            duration = time.monotonic() - start
            return BenchmarkResult(
                scenario_name=meta.name,
                passed=False,
                duration_seconds=duration,
                error_message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            duration = time.monotonic() - start
            return BenchmarkResult(
                scenario_name=meta.name,
                passed=False,
                duration_seconds=duration,
                error_message=f"Unexpected error: {exc}",
            )


def run_benchmarks(engine: "GovernanceEngine") -> BenchmarkReport:
    """Run all governance benchmark scenarios against *engine*.

    Convenience wrapper around ``BenchmarkSuite().run_all(engine)``.

    Parameters
    ----------
    engine:
        A ``GovernanceEngine`` instance to test against.

    Returns
    -------
    BenchmarkReport:
        Full benchmark results with a printable ``summary()``.
    """
    return BenchmarkSuite().run_all(engine)
