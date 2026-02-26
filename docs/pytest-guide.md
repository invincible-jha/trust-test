# pytest-aumos-governance — Developer Guide

This guide covers everything you need to write governance correctness tests
for AumOS agents using the `pytest-aumos-governance` plugin.

---

## Installation

```bash
pip install pytest-aumos-governance
```

The plugin auto-registers via the `pytest11` entry-point. No changes to
`conftest.py` are required.

---

## Core concepts

### Real engine, not mocks

Every fixture in this plugin provides a real `GovernanceEngine` instance.
Tests exercise actual governance logic — policy evaluation, trust checks,
budget accounting, and audit logging — not hand-written stubs.

This design means your tests will catch regressions in the governance layer
itself, not just in the code calling it.

### Fresh per test

Each test function that uses `governance_engine` (directly or through a
dependent fixture) receives its own isolated engine. State does not leak
between tests.

### Boundary testing

`assert_trust_required` always checks both sides of the trust boundary in a
single call. This catches two classes of bug simultaneously:

- Policy too permissive: action allowed below the required level
- Policy too restrictive: action denied at the required level

---

## Fixtures

### `governance_engine`

Provides a freshly constructed `GovernanceEngine` using `GovernanceConfig.default()`.

```python
def test_basic_check(governance_engine):
    decision = governance_engine.check_sync(
        action="file:read",
        context={"agent_id": "reader"},
    )
    assert decision is not None
```

### `trust_manager`

Shortcut to `governance_engine.trust`. Use when your test only needs to
manipulate trust levels.

```python
def test_trust_propagation(trust_manager):
    trust_manager.set_level("agent-a", 3, "default")
    level = trust_manager.get_level("agent-a", "default")
    assert level == 3
```

### `budget_manager`

Shortcut to `governance_engine.budget`. Use when your test only needs to
work with budget envelopes.

```python
def test_budget_depletion(budget_manager):
    budget_manager.create_envelope("llm", limit=10.0, period_seconds=3600)
    budget_manager.consume("llm", 10.0)
    result = budget_manager.check("llm", 0.01)
    assert not result.permitted
```

### `governed_agent(agent_id, trust_level, scope)`

Factory fixture that registers an agent with a trust level and returns
the `agent_id` string for use in assertions.

```python
def test_read_at_level_1(governance_engine, governed_agent):
    agent = governed_agent(agent_id="reader", trust_level=1)
    assert_governance_permitted(governance_engine, "file:read", agent_id=agent)
```

Default values: `agent_id="test-agent"`, `trust_level=2`, `scope="default"`.

### `budget_envelope(category, limit, period_seconds)`

Factory fixture that creates a budget envelope and returns the `category` string.

```python
def test_within_budget(governance_engine, budget_envelope):
    envelope = budget_envelope(category="network", limit=50.0)
    assert_budget_sufficient(governance_engine, envelope, amount=25.0)
```

Default values: `category="test"`, `limit=100.0`, `period_seconds=3600`.

---

## Assertion functions

Import from `pytest_governance.assertions`.

### `assert_trust_required(engine, action, required_level, agent_id, scope)`

Verifies that `action` requires exactly `required_level` trust by testing
both sides of the boundary.

```python
from pytest_governance.assertions import assert_trust_required

def test_delete_requires_level_4(governance_engine):
    assert_trust_required(governance_engine, action="file:delete", required_level=4)
```

### `assert_budget_sufficient(engine, category, amount)`

Asserts that the budget check for `amount` in `category` passes.

```python
from pytest_governance.assertions import assert_budget_sufficient

def test_small_llm_call_passes(governance_engine, budget_envelope):
    budget_envelope(category="llm", limit=10.0)
    assert_budget_sufficient(governance_engine, "llm", amount=1.0)
```

### `assert_budget_exceeded(engine, category, amount)`

Asserts that the budget check for `amount` in `category` fails.

```python
from pytest_governance.assertions import assert_budget_exceeded

def test_large_llm_call_blocked(governance_engine, budget_envelope):
    budget_envelope(category="llm", limit=5.0)
    assert_budget_exceeded(governance_engine, "llm", amount=10.0)
```

### `assert_consent_required(engine, action, agent_id)`

Asserts that `action` requires consent — the decision must be either fully
denied or the consent sub-decision must be denied.

```python
from pytest_governance.assertions import assert_consent_required

def test_pii_read_needs_consent(governance_engine):
    assert_consent_required(governance_engine, action="pii:read")
```

### `assert_governance_denied(engine, action, agent_id, context)`

Asserts that `action` is denied.

```python
from pytest_governance.assertions import assert_governance_denied

def test_admin_reset_denied_without_trust(governance_engine):
    assert_governance_denied(governance_engine, "admin:reset", agent_id="untrusted")
```

### `assert_governance_permitted(engine, action, agent_id, context)`

Asserts that `action` is permitted.

```python
from pytest_governance.assertions import assert_governance_permitted

def test_read_permitted(governance_engine, governed_agent):
    governed_agent(agent_id="reader", trust_level=1)
    assert_governance_permitted(governance_engine, "file:read", agent_id="reader")
```

### `assert_audit_contains(engine, action, count)`

Asserts that the audit log contains at least one record for `action`.
Optionally assert an exact `count`.

```python
from pytest_governance.assertions import assert_audit_contains

def test_audit_logged(governance_engine):
    governance_engine.check_sync(
        action="file:read",
        context={"agent_id": "reader"},
    )
    assert_audit_contains(governance_engine, "file:read")
    assert_audit_contains(governance_engine, "file:read", count=1)
```

---

## Fluent matcher

For assertions that need to inspect multiple properties of a single decision,
use the `GovernanceDecisionMatcher` via `expect_decision()`.

```python
from pytest_governance.matchers import expect_decision

def test_denial_detail(governance_engine):
    decision = governance_engine.check_sync(
        action="file:delete",
        context={"agent_id": "low-trust"},
    )
    (
        expect_decision(decision)
        .is_denied()
        .with_reason("trust")
        .at_trust_level(1)
        .requires_trust_level(4)
    )
```

### Available matcher methods

| Method | Description |
|---|---|
| `.is_permitted()` | Decision must be permitted |
| `.is_denied()` | Decision must be denied |
| `.with_reason(substring)` | `decision.reason` must contain the substring |
| `.without_reason(substring)` | `decision.reason` must NOT contain the substring |
| `.at_trust_level(level)` | `decision.trust.current_level` must equal `level` |
| `.requires_trust_level(level)` | `decision.trust.required_level` must equal `level` |
| `.with_budget_available(minimum)` | `decision.budget.available` must be >= `minimum` |
| `.with_consent_granted()` | `decision.consent.permitted` must be `True` |
| `.with_consent_denied()` | `decision.consent.permitted` must be `False` |

All methods return `self` for chaining. Failures produce descriptive `AssertionError` messages.

---

## Markers and CLI flag

### `@pytest.mark.governance`

Mark a test as a governance test. Combined with `--governance`, this enables
enhanced reporting and can be used to select governance tests selectively.

```python
import pytest

@pytest.mark.governance
def test_policy_enforcement(governance_engine):
    ...
```

Run only governance-marked tests:
```bash
pytest -m governance
```

### `--governance` flag

Activates governance marker auto-detection. Tests that use governance fixtures
but are not explicitly marked will be automatically marked during collection.

```bash
pytest --governance -v
```

---

## Example: full test module

```python
import pytest
from pytest_governance.assertions import (
    assert_trust_required,
    assert_budget_sufficient,
    assert_budget_exceeded,
    assert_governance_permitted,
    assert_audit_contains,
)
from pytest_governance.matchers import expect_decision


@pytest.mark.governance
class TestFileWritePolicy:
    def test_requires_trust_level_3(self, governance_engine):
        assert_trust_required(governance_engine, action="file:write", required_level=3)

    def test_budget_check_passes_within_limit(self, governance_engine, budget_envelope):
        budget_envelope(category="storage", limit=100.0)
        assert_budget_sufficient(governance_engine, "storage", amount=10.0)

    def test_budget_check_fails_over_limit(self, governance_engine, budget_envelope):
        budget_envelope(category="storage", limit=5.0)
        assert_budget_exceeded(governance_engine, "storage", amount=10.0)

    def test_audit_recorded(self, governance_engine, governed_agent):
        governed_agent(agent_id="writer", trust_level=3)
        governance_engine.check_sync(
            action="file:write",
            context={"agent_id": "writer"},
        )
        assert_audit_contains(governance_engine, "file:write", count=1)

    def test_denial_includes_trust_reason(self, governance_engine):
        decision = governance_engine.check_sync(
            action="file:write",
            context={"agent_id": "low-trust"},
        )
        (
            expect_decision(decision)
            .is_denied()
            .with_reason("trust")
        )
```

---

## Troubleshooting

**`ImportError: No module named 'aumos_governance'`**
Ensure `aumos-governance` is installed in the same environment as `pytest-aumos-governance`.

**Fixture not found**
The plugin auto-registers via `pytest11`. If fixtures are not available, verify
that `pytest-aumos-governance` is installed (`pip show pytest-aumos-governance`).

**`AttributeError` on `decision.trust` or `decision.budget`**
These sub-objects are only present when the relevant policy layer is active.
Check that the `GovernanceConfig` for your test engine enables the relevant
features.
