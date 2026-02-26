// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * Custom Vitest matchers for AumOS governance decisions.
 *
 * Register these matchers in your Vitest setup file:
 *
 * ```typescript
 * // vitest.setup.ts
 * import { expect } from 'vitest';
 * import { governanceMatchers } from '@aumos/vitest-governance';
 *
 * expect.extend(governanceMatchers());
 * ```
 *
 * After registration, the following matchers are available on any `expect()` call
 * that receives a `GovernanceDecision` object:
 *
 * - `toBeGovernancePermitted()`
 * - `toBeGovernanceDenied()`
 * - `toRequireTrustLevel(level)`
 * - `toHaveBudgetAvailable(amount)`
 */

import type { GovernanceDecision } from "@aumos/governance";

// ---------------------------------------------------------------------------
// Vitest augmentation — adds the custom matchers to the Assertion interface
// ---------------------------------------------------------------------------

/**
 * Custom matcher methods added to the Vitest `expect()` assertion interface.
 */
interface GovernanceMatchers<ReturnType = unknown> {
  /**
   * Assert that the received `GovernanceDecision` has `permitted === true`.
   *
   * @example
   * expect(decision).toBeGovernancePermitted();
   */
  toBeGovernancePermitted(): ReturnType;

  /**
   * Assert that the received `GovernanceDecision` has `permitted === false`.
   *
   * @example
   * expect(decision).toBeGovernanceDenied();
   */
  toBeGovernanceDenied(): ReturnType;

  /**
   * Assert that the action's required trust level recorded in the decision
   * equals `level`.
   *
   * @param level - The expected required trust level.
   *
   * @example
   * expect(decision).toRequireTrustLevel(3);
   */
  toRequireTrustLevel(level: number): ReturnType;

  /**
   * Assert that the available budget recorded in the decision is >= `amount`.
   *
   * @param amount - The minimum expected available budget.
   *
   * @example
   * expect(decision).toHaveBudgetAvailable(5.0);
   */
  toHaveBudgetAvailable(amount: number): ReturnType;
}

declare module "vitest" {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface Assertion<T = any> extends GovernanceMatchers<T> {}
  interface AsymmetricMatchersContaining extends GovernanceMatchers {}
}

// ---------------------------------------------------------------------------
// Matcher implementations
// ---------------------------------------------------------------------------

/**
 * The shape of a single matcher implementation as expected by `expect.extend()`.
 *
 * `received` is the value passed to `expect(received)`.
 */
type MatcherResult = {
  pass: boolean;
  message: () => string;
};

/**
 * Returns a record of custom Vitest matchers for `GovernanceDecision` objects.
 *
 * Pass the result to `expect.extend()` in your Vitest setup file.
 *
 * @returns An object whose keys are matcher names and whose values are
 *          matcher implementation functions compatible with `expect.extend()`.
 */
export function governanceMatchers(): Record<
  string,
  (received: GovernanceDecision, ...args: unknown[]) => MatcherResult
> {
  return {
    toBeGovernancePermitted(received: GovernanceDecision): MatcherResult {
      return {
        pass: received.permitted === true,
        message: () =>
          `Expected governance action to be permitted, but it was denied.\n` +
          `Reason: ${received.reason ?? "none"}`,
      };
    },

    toBeGovernanceDenied(received: GovernanceDecision): MatcherResult {
      return {
        pass: received.permitted === false,
        message: () =>
          `Expected governance action to be denied, but it was permitted.`,
      };
    },

    toRequireTrustLevel(
      received: GovernanceDecision,
      level: number,
    ): MatcherResult {
      const actualRequired = received.trust?.requiredLevel;
      return {
        pass: actualRequired === level,
        message: () =>
          `Expected required trust level to be ${String(level)}, ` +
          `but got ${String(actualRequired ?? "undefined")}.`,
      };
    },

    toHaveBudgetAvailable(
      received: GovernanceDecision,
      amount: number,
    ): MatcherResult {
      const available = received.budget?.available ?? 0;
      return {
        pass: available >= amount,
        message: () =>
          `Expected available budget >= ${String(amount)}, ` +
          `but got ${String(available)}.`,
      };
    },
  };
}
