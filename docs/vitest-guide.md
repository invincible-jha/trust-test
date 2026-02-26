# @aumos/vitest-governance — Developer Guide

This guide covers everything you need to write governance correctness tests
for AumOS agents using the `@aumos/vitest-governance` Vitest plugin.

---

## Installation

```bash
pnpm add -D @aumos/vitest-governance
```

`@aumos/governance` and `vitest` are peer dependencies — install them if not
already present:

```bash
pnpm add -D @aumos/governance vitest
```

---

## Setup

### 1. Configure Vitest to use the setup file

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    setupFiles: ['./vitest.setup.ts'],
  },
});
```

### 2. Register the custom matchers

```typescript
// vitest.setup.ts
import { expect } from 'vitest';
import { governanceMatchers } from '@aumos/vitest-governance';

expect.extend(governanceMatchers());
```

That is all the configuration required. The matchers are now available on
every `expect()` call in your test suite.

---

## Core concepts

### Real engine, not mocks

`createTestEngine()` returns a real `GovernanceEngine` instance. Tests exercise
actual governance logic rather than hand-written stubs. This means your tests
will catch regressions in the policy layer itself.

### Engine-per-test isolation

Create a new engine for each test using `createTestEngine()`. Because engines
hold in-memory state (trust levels, budget consumption, audit records), sharing
an engine across tests can cause flaky failures.

```typescript
// Preferred pattern — fresh engine per test
describe('my policy', () => {
  it('test one', async () => {
    const engine = createTestEngine();
    // ...
  });

  it('test two', async () => {
    const engine = createTestEngine();
    // ...
  });
});
```

### TypeScript strict mode

All exported types from this package are written with TypeScript strict mode
enabled. There are no `any` types in the public API.

---

## API reference

### `governanceMatchers()`

Returns the custom matcher record for use with `expect.extend()`.

```typescript
import { governanceMatchers } from '@aumos/vitest-governance';
expect.extend(governanceMatchers());
```

### `createTestEngine(overrides?)`

Creates a `GovernanceEngine` configured with test-safe defaults.
Pass `overrides` to customise specific config values.

```typescript
import { createTestEngine } from '@aumos/vitest-governance';

const engine = createTestEngine();
const engineWithCustomAudit = createTestEngine({ audit: { backend: 'memory' } });
```

### `setTrustLevel(engine, agentId, level, scope?)`

Sets the trust level for an agent.

```typescript
import { setTrustLevel } from '@aumos/vitest-governance';

setTrustLevel(engine, 'agent-1', 3);
setTrustLevel(engine, 'agent-2', 1, 'restricted');
```

### `createBudget(engine, category, limit)`

Creates a budget envelope for a category.

```typescript
import { createBudget } from '@aumos/vitest-governance';

createBudget(engine, 'llm', 10.0);
createBudget(engine, 'network', 50.0);
```

---

## Custom matchers

After calling `expect.extend(governanceMatchers())`, the following matchers
are available on any `expect(decision)` call where `decision` is a
`GovernanceDecision` object.

### `toBeGovernancePermitted()`

Asserts that `decision.permitted === true`.

```typescript
expect(decision).toBeGovernancePermitted();
```

Failure message example:
> Expected governance action to be permitted, but it was denied.
> Reason: insufficient trust level

### `toBeGovernanceDenied()`

Asserts that `decision.permitted === false`.

```typescript
expect(decision).toBeGovernanceDenied();
```

Failure message example:
> Expected governance action to be denied, but it was permitted.

### `toRequireTrustLevel(level)`

Asserts that `decision.trust.requiredLevel === level`.

```typescript
expect(decision).toRequireTrustLevel(3);
```

Failure message example:
> Expected required trust level to be 3, but got 2.

### `toHaveBudgetAvailable(amount)`

Asserts that `decision.budget.available >= amount`.

```typescript
expect(decision).toHaveBudgetAvailable(5.0);
```

Failure message example:
> Expected available budget >= 5, but got 2.5.

---

## Examples

### Basic permit/deny test

```typescript
import { describe, it, expect } from 'vitest';
import { createTestEngine, setTrustLevel } from '@aumos/vitest-governance';

describe('file:write policy', () => {
  it('permits write at trust level 3', async () => {
    const engine = createTestEngine();
    setTrustLevel(engine, 'agent-1', 3);

    const decision = await engine.check({
      action: 'file:write',
      context: { agentId: 'agent-1' },
    });

    expect(decision).toBeGovernancePermitted();
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

### Trust level boundary test

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { createTestEngine, setTrustLevel } from '@aumos/vitest-governance';
import type { GovernanceEngine } from '@aumos/governance';

describe('admin:reset trust boundary', () => {
  let engine: GovernanceEngine;

  beforeEach(() => {
    engine = createTestEngine();
  });

  it.each([
    [1, false],
    [2, false],
    [3, false],
    [4, true],
    [5, true],
  ])('trust level %i → permitted: %s', async (level, expectedPermitted) => {
    setTrustLevel(engine, 'agent', level);

    const decision = await engine.check({
      action: 'admin:reset',
      context: { agentId: 'agent' },
    });

    if (expectedPermitted) {
      expect(decision).toBeGovernancePermitted();
    } else {
      expect(decision).toBeGovernanceDenied();
      expect(decision).toRequireTrustLevel(4);
    }
  });
});
```

### Budget enforcement test

```typescript
import { describe, it, expect } from 'vitest';
import { createTestEngine, setTrustLevel, createBudget } from '@aumos/vitest-governance';

describe('LLM budget policy', () => {
  it('permits call within budget', async () => {
    const engine = createTestEngine();
    setTrustLevel(engine, 'agent-1', 2);
    createBudget(engine, 'llm', 10.0);

    const decision = await engine.check({
      action: 'llm:call',
      context: { agentId: 'agent-1', estimatedCost: 1.0 },
    });

    expect(decision).toBeGovernancePermitted();
    expect(decision).toHaveBudgetAvailable(9.0);
  });

  it('denies call exceeding budget', async () => {
    const engine = createTestEngine();
    setTrustLevel(engine, 'agent-1', 2);
    createBudget(engine, 'llm', 5.0);

    const decision = await engine.check({
      action: 'llm:call',
      context: { agentId: 'agent-1', estimatedCost: 10.0 },
    });

    expect(decision).toBeGovernanceDenied();
  });
});
```

### Combining matchers

```typescript
import { describe, it, expect } from 'vitest';
import { createTestEngine } from '@aumos/vitest-governance';

describe('combined matcher usage', () => {
  it('reports correct trust metadata on denial', async () => {
    const engine = createTestEngine();
    // agent at default trust level 0 — below any meaningful action

    const decision = await engine.check({
      action: 'file:delete',
      context: { agentId: 'untrusted-agent' },
    });

    expect(decision).toBeGovernanceDenied();
    expect(decision).toRequireTrustLevel(4);
  });
});
```

---

## TypeScript type augmentation

The package augments the Vitest `Assertion` and `AsymmetricMatchersContaining`
interfaces, so your IDE will show the custom matchers in autocomplete after
calling `expect.extend(governanceMatchers())`.

If you see TypeScript errors on the matcher names, ensure the
`@aumos/vitest-governance` package is imported in at least one file that is
included in your `tsconfig.json`.

---

## Building the package

```bash
cd typescript
pnpm install
pnpm build        # produces ./dist/index.js and ./dist/index.d.ts
pnpm typecheck    # runs tsc --noEmit
```

---

## Troubleshooting

**Matchers not recognised by TypeScript**
Ensure `@aumos/vitest-governance` is in your `devDependencies` and that
`vitest.setup.ts` is included in your `tsconfig.json` `include` array.

**`Cannot find module '@aumos/governance'`**
Install the peer dependency: `pnpm add -D @aumos/governance`.

**`expect(decision).toBeGovernancePermitted is not a function` at runtime**
`expect.extend(governanceMatchers())` must run before any test that uses the
matchers. Verify that your setup file path is correctly listed in
`vitest.config.ts` under `test.setupFiles`.
