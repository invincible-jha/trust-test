# Governance Coverage

## What is Governance Coverage?

Governance coverage is the governance equivalent of code coverage.

Just as code coverage measures what percentage of your code paths are exercised
by tests, governance coverage measures what percentage of your agent's actions
are governed by each of the four governance pillars: **Trust**, **Budget**,
**Consent**, and **Audit**.

If your agents have 95% code coverage but 40% governance coverage, you have a
problem. The code works — but most of what your agents do is ungoverned.

---

## The Four Pillars

Every action an agent takes can be checked against four independent governance
controls. Each missed control is a gap in your governance posture.

### Trust

Was the agent's trust level verified before the action was allowed?

A trust check ensures the agent has earned the right to perform this action.
Without it, any agent — regardless of how it was configured or what it has
done — can attempt the action.

### Budget

Was the agent's resource budget checked before the action was allowed?

A budget check ensures the agent cannot exhaust shared resources without
explicit allocation. Without it, a single runaway agent can consume unbounded
compute, token spend, or API quota.

### Consent

Was explicit user or owner consent verified before the action was allowed?

A consent check ensures that data-sensitive or irreversible actions are only
taken with the knowledge of the appropriate principal. Without it, agents may
act on behalf of users without their awareness.

### Audit

Was the outcome of the action written to an immutable audit log?

An audit log entry ensures the action is visible, traceable, and attributable.
Without it, there is no forensic record if something goes wrong.

---

## Collecting ActionTraces

A governance coverage report is computed from a sequence of `ActionTrace`
records. Each `ActionTrace` captures whether a single action invocation had
each of the four governance checks.

There are three ways to collect `ActionTrace` records.

### 1. Audit-log parsing

If your `GovernanceEngine` writes structured audit log entries, parse them
after a test run or staging session to extract governance check outcomes.

```python
from governance_coverage import ActionTrace

def trace_from_audit_entry(entry: dict) -> ActionTrace:
    return ActionTrace(
        action_id=entry["id"],
        action_name=entry["action"],
        has_trust_check=entry.get("trust_check_performed", False),
        has_budget_check=entry.get("budget_check_performed", False),
        has_consent_check=entry.get("consent_check_performed", False),
        has_audit_log=True,  # If it's in the audit log, audit is covered
    )
```

### 2. Test instrumentation

Instrument your test suite to record governance checks as each test runs.
The `pytest-aumos-governance` plugin exposes a `governance_engine` fixture
whose audit backend can be queried after each test.

```python
import pytest
from pytest_governance import assert_audit_contains
from governance_coverage import ActionTrace, compute_governance_coverage

def test_my_scenario(governance_engine):
    governance_engine.check({"action": "file:write", "context": {"agentId": "a1"}})
    governance_engine.check({"action": "data:export", "context": {"agentId": "a1"}})

    entries = governance_engine.audit.entries()
    traces = [
        ActionTrace(
            action_id=e.id,
            action_name=e.action,
            has_trust_check=e.trust_check_performed,
            has_budget_check=e.budget_check_performed,
            has_consent_check=e.consent_check_performed,
            has_audit_log=True,
        )
        for e in entries
    ]
    report = compute_governance_coverage(traces)
    assert report.overall_coverage_pct >= 80.0
```

### 3. Manual annotation

For smaller action sets or acceptance testing, annotate traces by hand:

```python
from governance_coverage import ActionTrace

traces = [
    ActionTrace("id-1", "file:read",    True,  True,  False, True),
    ActionTrace("id-2", "llm:call",     True,  True,  False, True),
    ActionTrace("id-3", "data:export",  True,  False, True,  True),
    ActionTrace("id-4", "network:post", False, True,  False, False),
]
```

---

## Interpreting the Report

```
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
```

### Overall Coverage

The headline figure. It is the unweighted mean of the four pillar percentages.
Use this as the single threshold in CI.

A target of **80% or higher** is a reasonable baseline for agents in production.
Critical agents (those with write access, external API calls, or access to
personal data) should aim for **100% audit coverage** as a hard requirement.

### Per-Pillar Coverage

Each pillar is reported independently so you can see exactly where gaps lie.

- **Trust at 100%, Audit at 100%** — the two minimum safety pillars are fully
  covered. Uncovered actions in budget or consent still warrant investigation
  but represent lower risk.
- **Audit below 100%** — some actions leave no forensic trace. This is the
  highest-risk gap and should be resolved before production deployment.
- **Trust below 100%** — some actions bypass trust verification. Any of these
  actions could be performed by an agent at any trust level.

### Uncovered Actions

An action appears in the uncovered list if it is missing **either** a trust
check **or** an audit log entry. These two pillars represent the minimum safety
bar. Every action on this list needs attention.

---

## Integration with CI

Add a governance coverage check to your CI pipeline to fail the build
automatically when coverage drops below a threshold.

### Python — pytest + coverage check

```python
# tests/test_governance_coverage.py
from governance_coverage import (
    ActionTrace,
    compute_governance_coverage,
    format_coverage_report,
)

GOVERNANCE_COVERAGE_THRESHOLD = 80.0

def collect_traces() -> list[ActionTrace]:
    """Return traces from your audit log, test run, or manual annotation."""
    ...

def test_governance_coverage_meets_threshold():
    traces = collect_traces()
    report = compute_governance_coverage(traces)
    print(format_coverage_report(report))
    assert report.overall_coverage_pct >= GOVERNANCE_COVERAGE_THRESHOLD, (
        f"Governance coverage {report.overall_coverage_pct}% "
        f"is below the {GOVERNANCE_COVERAGE_THRESHOLD}% threshold.\n"
        f"Uncovered actions: {list(report.uncovered_actions)}"
    )
```

Run it as part of your normal test suite:

```bash
pytest tests/test_governance_coverage.py --tb=short
```

### TypeScript — Vitest + coverage check

```typescript
// tests/governance-coverage.test.ts
import { describe, it, expect } from "vitest";
import {
  computeGovernanceCoverage,
  formatCoverageReport,
  type ActionTrace,
} from "../src/governance-coverage";

const GOVERNANCE_COVERAGE_THRESHOLD = 80;

function collectTraces(): ActionTrace[] {
  // Return traces from your audit log, test run, or manual annotation.
  return [];
}

describe("governance coverage", () => {
  it(`meets the ${String(GOVERNANCE_COVERAGE_THRESHOLD)}% threshold`, () => {
    const traces = collectTraces();
    const report = computeGovernanceCoverage(traces);

    console.log(formatCoverageReport(report));

    expect(report.overallCoveragePct).toBeGreaterThanOrEqual(
      GOVERNANCE_COVERAGE_THRESHOLD,
    );
  });
});
```

### GitHub Actions example

```yaml
# .github/workflows/ci.yml
jobs:
  governance-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install -e "python/.[dev]" aumos-governance

      - name: Run governance coverage check
        run: pytest tests/test_governance_coverage.py -v
```

The job fails if `overall_coverage_pct` is below the threshold, blocking the
merge — exactly the same way a code coverage gate works.

---

## Example Output

### Full coverage (ideal)

```
Governance Coverage Report
========================================
Total Actions: 5

Pillar Coverage:
  Trust:   100.0% (5/5)
  Budget:  100.0% (5/5)
  Consent: 100.0% (5/5)
  Audit:   100.0% (5/5)

Overall Coverage: 100.0%
```

### Mixed coverage (needs attention)

```
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
```

### Empty trace set

```
Governance Coverage Report
========================================
Total Actions: 0

Pillar Coverage:
  Trust:     0.0% (0/0)
  Budget:    0.0% (0/0)
  Consent:   0.0% (0/0)
  Audit:     0.0% (0/0)

Overall Coverage: 0.0%
```

An empty trace set is treated as zero coverage, not as a passing state.
Ensure your trace collection is working before interpreting results.

---

## Test-Driven Governance

Governance coverage gives teams a concrete, measurable way to adopt
**test-driven governance (TDG)** — a practice where governance requirements
are specified before implementation, and coverage gates enforce compliance.

The workflow mirrors test-driven development:

1. **Define your governance requirements** — which actions require which pillars?
2. **Write the governance tests first** — use `pytest-aumos-governance` or
   `@aumos/vitest-governance` to specify expected decisions.
3. **Implement the actions** — wire each action to the `GovernanceEngine`.
4. **Collect traces and compute coverage** — run `compute_governance_coverage`.
5. **Enforce the gate in CI** — fail the build when coverage drops below your
   threshold.

Just as code coverage answered "did we write tests for this code?", governance
coverage answers "did we govern this action?". Both are necessary. Neither alone
is sufficient.

> Governance coverage is the trust equivalent of a test coverage report.
> You would not ship code with 40% test coverage. Do not ship agents with
> 40% governance coverage.
