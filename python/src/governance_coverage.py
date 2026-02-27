# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""Governance coverage metric for AumOS agent action traces.

Governance coverage is the governance equivalent of code coverage.  It answers
the question: "Of all the actions my agent performed, what fraction were
governed by each pillar?"

The four pillars are:

- **Trust**   — was a trust-level check performed before the action?
- **Budget**  — was a budget-envelope check performed before the action?
- **Consent** — was explicit consent verified before the action?
- **Audit**   — was the action outcome written to an audit log?

Call :func:`compute_governance_coverage` with a sequence of
:class:`ActionTrace` records to obtain a :class:`GovernanceCoverageReport`.
Use :func:`format_coverage_report` to render the report as human-readable text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ActionTrace:
    """Trace record for a single agent action.

    Attributes:
        action_id:        Unique identifier for this action invocation.
        action_name:      Human-readable name of the action (e.g. ``"file:write"``).
        has_trust_check:  ``True`` if a trust-level check was performed.
        has_budget_check: ``True`` if a budget-envelope check was performed.
        has_consent_check:``True`` if explicit consent was verified.
        has_audit_log:    ``True`` if the action outcome was written to an audit log.
    """

    action_id: str
    action_name: str
    has_trust_check: bool
    has_budget_check: bool
    has_consent_check: bool
    has_audit_log: bool


@dataclass(frozen=True)
class GovernanceCoverageReport:
    """Report of governance coverage across a set of agent action traces.

    Attributes:
        total_actions:         Number of action traces evaluated.
        trust_checked:         Actions that had a trust check.
        budget_checked:        Actions that had a budget check.
        consent_checked:       Actions that had a consent check.
        audit_logged:          Actions that produced an audit log entry.
        trust_coverage_pct:    Trust pillar coverage as a percentage (0–100).
        budget_coverage_pct:   Budget pillar coverage as a percentage (0–100).
        consent_coverage_pct:  Consent pillar coverage as a percentage (0–100).
        audit_coverage_pct:    Audit pillar coverage as a percentage (0–100).
        overall_coverage_pct:  Mean of the four pillar percentages (0–100).
        uncovered_actions:     Names of actions missing a trust check **or** an
                               audit log entry (the two minimum safety pillars).
    """

    total_actions: int
    trust_checked: int
    budget_checked: int
    consent_checked: int
    audit_logged: int
    trust_coverage_pct: float
    budget_coverage_pct: float
    consent_coverage_pct: float
    audit_coverage_pct: float
    overall_coverage_pct: float
    uncovered_actions: Sequence[str]


def compute_governance_coverage(traces: Sequence[ActionTrace]) -> GovernanceCoverageReport:
    """Compute governance coverage from a sequence of action traces.

    Coverage is computed per-pillar (trust, budget, consent, audit) as
    the percentage of traced actions that have the corresponding governance
    check.  Overall coverage is the unweighted mean of all four pillars.

    An action is considered *uncovered* when it lacks **either** a trust check
    **or** an audit log entry — the two pillars that represent the minimum
    safety bar for any governed action.

    Args:
        traces: The action traces to analyse.  May be empty.

    Returns:
        A :class:`GovernanceCoverageReport` containing per-pillar counts,
        percentages, overall coverage, and the list of uncovered action names.
    """
    total = len(traces)
    if total == 0:
        return GovernanceCoverageReport(
            total_actions=0,
            trust_checked=0,
            budget_checked=0,
            consent_checked=0,
            audit_logged=0,
            trust_coverage_pct=0.0,
            budget_coverage_pct=0.0,
            consent_coverage_pct=0.0,
            audit_coverage_pct=0.0,
            overall_coverage_pct=0.0,
            uncovered_actions=[],
        )

    trust_checked = sum(1 for trace in traces if trace.has_trust_check)
    budget_checked = sum(1 for trace in traces if trace.has_budget_check)
    consent_checked = sum(1 for trace in traces if trace.has_consent_check)
    audit_logged = sum(1 for trace in traces if trace.has_audit_log)

    # An action is uncovered if it is missing a trust check OR an audit log.
    uncovered_actions = [
        trace.action_name
        for trace in traces
        if not (trace.has_trust_check and trace.has_audit_log)
    ]

    trust_pct = (trust_checked / total) * 100
    budget_pct = (budget_checked / total) * 100
    consent_pct = (consent_checked / total) * 100
    audit_pct = (audit_logged / total) * 100
    overall_pct = (trust_pct + budget_pct + consent_pct + audit_pct) / 4

    return GovernanceCoverageReport(
        total_actions=total,
        trust_checked=trust_checked,
        budget_checked=budget_checked,
        consent_checked=consent_checked,
        audit_logged=audit_logged,
        trust_coverage_pct=round(trust_pct, 1),
        budget_coverage_pct=round(budget_pct, 1),
        consent_coverage_pct=round(consent_pct, 1),
        audit_coverage_pct=round(audit_pct, 1),
        overall_coverage_pct=round(overall_pct, 1),
        uncovered_actions=uncovered_actions,
    )


def format_coverage_report(report: GovernanceCoverageReport) -> str:
    """Format a governance coverage report as a human-readable string.

    Args:
        report: The report produced by :func:`compute_governance_coverage`.

    Returns:
        A multi-line string suitable for printing to stdout or writing to a
        CI log.  Uncovered actions are listed individually when present.

    Example output::

        Governance Coverage Report
        ========================================
        Total Actions: 10

        Pillar Coverage:
          Trust:   100.0% (10/10)
          Budget:   80.0% (8/10)
          Consent:  70.0% (7/10)
          Audit:   100.0% (10/10)

        Overall Coverage: 87.5%

        Uncovered Actions (2):
          - data:export
          - network:request
    """
    total = report.total_actions
    lines: list[str] = [
        "Governance Coverage Report",
        "=" * 40,
        f"Total Actions: {total}",
        "",
        "Pillar Coverage:",
        f"  Trust:   {report.trust_coverage_pct:5.1f}%"
        f" ({report.trust_checked}/{total})",
        f"  Budget:  {report.budget_coverage_pct:5.1f}%"
        f" ({report.budget_checked}/{total})",
        f"  Consent: {report.consent_coverage_pct:5.1f}%"
        f" ({report.consent_checked}/{total})",
        f"  Audit:   {report.audit_coverage_pct:5.1f}%"
        f" ({report.audit_logged}/{total})",
        "",
        f"Overall Coverage: {report.overall_coverage_pct:.1f}%",
    ]
    if report.uncovered_actions:
        lines.append("")
        lines.append(f"Uncovered Actions ({len(report.uncovered_actions)}):")
        for action_name in report.uncovered_actions:
            lines.append(f"  - {action_name}")
    return "\n".join(lines)
