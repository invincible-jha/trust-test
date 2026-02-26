// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * @aumos/vitest-governance
 *
 * Vitest plugin providing custom matchers and test helpers for AumOS governance testing.
 *
 * ## Quick start
 *
 * Register the matchers in your Vitest setup file:
 *
 * ```typescript
 * // vitest.setup.ts
 * import { expect } from 'vitest';
 * import { governanceMatchers } from '@aumos/vitest-governance';
 *
 * expect.extend(governanceMatchers());
 * ```
 *
 * Then in your tests:
 *
 * ```typescript
 * import { describe, it, expect } from 'vitest';
 * import { createTestEngine, setTrustLevel } from '@aumos/vitest-governance';
 *
 * describe('file:write policy', () => {
 *   it('permits write at trust level 3', async () => {
 *     const engine = createTestEngine();
 *     setTrustLevel(engine, 'agent-1', 3);
 *
 *     const decision = await engine.check({
 *       action: 'file:write',
 *       context: { agentId: 'agent-1' },
 *     });
 *
 *     expect(decision).toBeGovernancePermitted();
 *     expect(decision).toRequireTrustLevel(3);
 *   });
 * });
 * ```
 *
 * @packageDocumentation
 */

// Matchers
export { governanceMatchers } from "./matchers.js";

// Helpers
export { createTestEngine, setTrustLevel, createBudget } from "./helpers.js";
