# trust-test

Testing framework with governance-specific assertions for AumOS.

Provides two independent plugins — one for Python/pytest and one for TypeScript/Vitest —
so that any team in the AumOS ecosystem can write high-confidence governance tests
regardless of their primary language.

---

## Packages

| Package | Language | Registry |
|---|---|---|
| `pytest-aumos-governance` | Python 3.10+ | PyPI |
| `@aumos/vitest-governance` | TypeScript / ESM | npm |

The two packages share no runtime dependency on each other. Install only what you need.

---

## Python — pytest-aumos-governance

### Installation

```bash
pip install pytest-aumos-governance
```

### Quick start

```python
# conftest.py — no extra config needed; the plugin auto-registers via pytest11

# test_my_agent.py
from pytest_governance.assertions import (
    assert_trust_required,
    assert_budget_sufficient,
    assert_governance_permitted,
)

def test_file_write_requires_trust_level_3(governance_engine):
    assert_trust_required(governance_engine, action="file:write", required_level=3)

def test_llm_call_within_budget(governance_engine, budget_envelope):
    budget_envelope(category="llm", limit=10.0)
    assert_budget_sufficient(governance_engine, category="llm", amount=5.0)

def test_read_permitted_at_default_trust(governance_engine, governed_agent):
    governed_agent(agent_id="reader", trust_level=1)
    assert_governance_permitted(governance_engine, action="file:read", agent_id="reader")
```

### Available fixtures

| Fixture | Description |
|---|---|
| `governance_engine` | Fresh `GovernanceEngine` per test |
| `trust_manager` | `governance_engine.trust` shortcut |
| `budget_manager` | `governance_engine.budget` shortcut |
| `governed_agent` | Factory: creates an agent with a given trust level |
| `budget_envelope` | Factory: creates a budget envelope for a category |

### Assertion functions

| Function | Description |
|---|---|
| `assert_trust_required(engine, action, level)` | Tests both sides of the trust boundary |
| `assert_budget_sufficient(engine, category, amount)` | Budget check must pass |
| `assert_budget_exceeded(engine, category, amount)` | Budget check must fail |
| `assert_consent_required(engine, action)` | Action must require consent |
| `assert_governance_denied(engine, action)` | Decision must be denied |
| `assert_governance_permitted(engine, action)` | Decision must be permitted |
| `assert_audit_contains(engine, action, count)` | Audit log must contain entries |

### Fluent matcher

```python
from pytest_governance.matchers import expect_decision

def test_decision_detail(governance_engine):
    decision = governance_engine.check_sync(
        action="file:delete",
        context={"agent_id": "low-trust-agent"}
    )
    (
        expect_decision(decision)
        .is_denied()
        .with_reason("trust")
    )
```

### CLI flag and marker

```bash
pytest --governance          # activates the governance marker collection report
```

```python
import pytest

@pytest.mark.governance
def test_something_governance_related(governance_engine):
    ...
```

---

## TypeScript — @aumos/vitest-governance

### Installation

```bash
pnpm add -D @aumos/vitest-governance
```

### Setup (vitest.config.ts)

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    setupFiles: ['./vitest.setup.ts'],
  },
});
```

```typescript
// vitest.setup.ts
import { expect } from 'vitest';
import { governanceMatchers } from '@aumos/vitest-governance';

expect.extend(governanceMatchers());
```

### Quick start

```typescript
import { describe, it, expect } from 'vitest';
import { createTestEngine, setTrustLevel } from '@aumos/vitest-governance';

describe('file:write governance', () => {
  it('permits write at trust level 3', async () => {
    const engine = createTestEngine();
    setTrustLevel(engine, 'agent-1', 3);

    const decision = await engine.check({
      action: 'file:write',
      context: { agentId: 'agent-1' },
    });

    expect(decision).toBeGovernancePermitted();
    expect(decision).toRequireTrustLevel(3);
  });

  it('denies write below trust level 3', async () => {
    const engine = createTestEngine();
    setTrustLevel(engine, 'agent-1', 2);

    const decision = await engine.check({
      action: 'file:write',
      context: { agentId: 'agent-1' },
    });

    expect(decision).toBeGovernanceDenied();
  });
});
```

### Custom matchers

| Matcher | Description |
|---|---|
| `toBeGovernancePermitted()` | Decision must have `permitted === true` |
| `toBeGovernanceDenied()` | Decision must have `permitted === false` |
| `toRequireTrustLevel(level)` | Decision must record the given required trust level |
| `toHaveBudgetAvailable(amount)` | Decision budget must show `available >= amount` |

### Helper functions

| Function | Description |
|---|---|
| `createTestEngine(overrides?)` | Creates a `GovernanceEngine` with test defaults |
| `setTrustLevel(engine, agentId, level, scope?)` | Sets trust level for an agent |
| `createBudget(engine, category, limit)` | Creates a budget envelope |

---

## Design Principles

**Real engine, not mocks.** Both plugins provide a real `GovernanceEngine` instance
so tests exercise actual governance logic rather than hand-written stubs.

**Boundary testing.** `assert_trust_required` always checks both sides of the
required level (level - 1 and level) in a single call to prevent false negatives.

**Language independence.** Neither package depends on the other at runtime.
Polyglot teams can adopt one without the other.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
Copyright (c) 2026 MuVeraAI Corporation.
