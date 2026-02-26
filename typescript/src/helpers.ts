// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * Test helper utilities for AumOS governance testing with Vitest.
 *
 * These helpers provide lightweight wrappers around `GovernanceEngine` operations
 * that are commonly needed when writing governance tests. They are intentionally
 * thin — they delegate all logic to the engine and simply reduce boilerplate in
 * test files.
 *
 * @example
 * ```typescript
 * import { createTestEngine, setTrustLevel, createBudget } from '@aumos/vitest-governance';
 *
 * const engine = createTestEngine();
 * setTrustLevel(engine, 'agent-1', 3);
 * createBudget(engine, 'llm', 10.0);
 *
 * const decision = await engine.check({
 *   action: 'file:write',
 *   context: { agentId: 'agent-1' },
 * });
 * ```
 */

import {
  GovernanceConfig,
  GovernanceEngine,
} from "@aumos/governance";

// ---------------------------------------------------------------------------
// Engine factory
// ---------------------------------------------------------------------------

/**
 * Create a `GovernanceEngine` configured with test-safe defaults.
 *
 * Merges `overrides` on top of `GovernanceConfig.defaults()` so individual
 * tests can tune specific settings without constructing a full config object.
 *
 * @param overrides - Partial `GovernanceConfig` values to override the defaults.
 * @returns A fully initialised `GovernanceEngine` ready for use in tests.
 *
 * @example
 * ```typescript
 * // Default test engine
 * const engine = createTestEngine();
 *
 * // Engine with a custom audit backend
 * const engine = createTestEngine({ audit: { backend: 'memory' } });
 * ```
 */
export function createTestEngine(
  overrides?: Partial<GovernanceConfig>,
): GovernanceEngine {
  const config: GovernanceConfig = {
    ...GovernanceConfig.defaults(),
    ...(overrides ?? {}),
  };
  return new GovernanceEngine(config);
}

// ---------------------------------------------------------------------------
// Trust helpers
// ---------------------------------------------------------------------------

/**
 * Set the trust level for an agent within the engine's trust store.
 *
 * @param engine  - A `GovernanceEngine` instance (e.g. from `createTestEngine()`).
 * @param agentId - The identifier of the agent to configure.
 * @param level   - The trust level to assign (integer, typically 0–5).
 * @param scope   - Optional trust scope. Defaults to the engine's default scope
 *                  when omitted.
 *
 * @example
 * ```typescript
 * setTrustLevel(engine, 'agent-a', 3);
 * setTrustLevel(engine, 'agent-b', 1, 'restricted');
 * ```
 */
export function setTrustLevel(
  engine: GovernanceEngine,
  agentId: string,
  level: number,
  scope?: string,
): void {
  engine.trust.setLevel(agentId, level, scope);
}

// ---------------------------------------------------------------------------
// Budget helpers
// ---------------------------------------------------------------------------

/**
 * Create a budget envelope in the engine's budget manager.
 *
 * @param engine   - A `GovernanceEngine` instance.
 * @param category - The budget category name (e.g. `"llm"`, `"network"`).
 * @param limit    - The maximum amount allowed within the envelope's period.
 *
 * @example
 * ```typescript
 * createBudget(engine, 'llm', 10.0);
 * ```
 */
export function createBudget(
  engine: GovernanceEngine,
  category: string,
  limit: number,
): void {
  engine.budget.createEnvelope(category, limit);
}
