// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * vitest_example.ts — Vitest example for @aumos/vitest-governance
 *
 * Demonstrates how to:
 * - Register the custom governance matchers in a setup file
 * - Use createTestEngine() to build a test engine with safe defaults
 * - Use setTrustLevel() and createBudget() to configure test state
 * - Assert governance outcomes with toBeGovernancePermitted(),
 *   toBeGovernanceDenied(), toRequireTrustLevel(), and toHaveBudgetAvailable()
 *
 * Run with:
 *   vitest run trust-test/examples/vitest_example.ts
 *
 * Register matchers globally in your vitest.setup.ts:
 *   import { expect } from 'vitest';
 *   import { governanceMatchers } from '@aumos/vitest-governance';
 *   expect.extend(governanceMatchers());
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  createBudget,
  createTestEngine,
  governanceMatchers,
  setTrustLevel,
} from "@aumos/vitest-governance";
import type { GovernanceEngine } from "@aumos/governance";

// Register the custom matchers for this example file.
// In a real project, move this call to vitest.setup.ts so it applies globally.
expect.extend(governanceMatchers());

// ---------------------------------------------------------------------------
// Trust level tests
// ---------------------------------------------------------------------------

describe("trust level enforcement", () => {
  let engine: GovernanceEngine;

  beforeEach(() => {
    engine = createTestEngine();
  });

  it("permits file:read at trust level 2", async () => {
    setTrustLevel(engine, "reader-agent", 2);

    const decision = await engine.check({
      action: "file:read",
      context: { agentId: "reader-agent" },
    });

    expect(decision).toBeGovernancePermitted();
    expect(decision).toRequireTrustLevel(2);
  });

  it("denies file:write at trust level 1", async () => {
    setTrustLevel(engine, "low-trust-agent", 1);

    const decision = await engine.check({
      action: "file:write",
      context: { agentId: "low-trust-agent" },
    });

    expect(decision).toBeGovernanceDenied();
    expect(decision).toRequireTrustLevel(3);
  });

  it("permits file:write at trust level 3", async () => {
    setTrustLevel(engine, "authorized-agent", 3);

    const decision = await engine.check({
      action: "file:write",
      context: { agentId: "authorized-agent" },
    });

    expect(decision).toBeGovernancePermitted();
  });

  it("denies all actions for an agent at trust level 0", async () => {
    setTrustLevel(engine, "untrusted", 0);

    const readDecision = await engine.check({
      action: "file:read",
      context: { agentId: "untrusted" },
    });
    const writeDecision = await engine.check({
      action: "file:write",
      context: { agentId: "untrusted" },
    });

    expect(readDecision).toBeGovernanceDenied();
    expect(writeDecision).toBeGovernanceDenied();
  });
});

// ---------------------------------------------------------------------------
// Budget enforcement tests
// ---------------------------------------------------------------------------

describe("budget enforcement", () => {
  let engine: GovernanceEngine;

  beforeEach(() => {
    engine = createTestEngine();
    // Pre-configure budget envelopes shared across tests in this suite.
    createBudget(engine, "llm", 10.0);
    createBudget(engine, "network", 5.0);
  });

  it("reports budget available when within limit", async () => {
    setTrustLevel(engine, "budget-agent", 3);

    const decision = await engine.check({
      action: "llm:invoke",
      context: { agentId: "budget-agent", estimatedCost: 3.0 },
    });

    expect(decision).toBeGovernancePermitted();
    expect(decision).toHaveBudgetAvailable(3.0);
  });

  it("denies action when estimated cost exceeds budget", async () => {
    setTrustLevel(engine, "budget-agent", 3);

    const decision = await engine.check({
      action: "llm:invoke",
      context: { agentId: "budget-agent", estimatedCost: 15.0 },
    });

    expect(decision).toBeGovernanceDenied();
  });

  it("permits action at exact budget limit boundary", async () => {
    setTrustLevel(engine, "boundary-agent", 3);

    const decision = await engine.check({
      action: "llm:invoke",
      context: { agentId: "boundary-agent", estimatedCost: 10.0 },
    });

    expect(decision).toBeGovernancePermitted();
    expect(decision).toHaveBudgetAvailable(0.0);
  });

  it("uses a separate envelope per category", async () => {
    setTrustLevel(engine, "multi-budget-agent", 3);

    const llmDecision = await engine.check({
      action: "llm:invoke",
      context: { agentId: "multi-budget-agent", estimatedCost: 4.0 },
    });
    const networkDecision = await engine.check({
      action: "network:fetch",
      context: { agentId: "multi-budget-agent", estimatedCost: 4.0 },
    });

    // Both should be permitted — they draw from separate envelopes.
    expect(llmDecision).toBeGovernancePermitted();
    expect(networkDecision).toBeGovernancePermitted();
  });
});

// ---------------------------------------------------------------------------
// Governance policy scenario tests
// ---------------------------------------------------------------------------

describe("governance scenarios", () => {
  it("trust-and-budget combined gate: denied on trust, budget irrelevant", async () => {
    const engine = createTestEngine();
    createBudget(engine, "llm", 100.0); // plenty of budget
    setTrustLevel(engine, "weak-agent", 1); // but trust is too low

    const decision = await engine.check({
      action: "file:write",
      context: { agentId: "weak-agent", estimatedCost: 0.5 },
    });

    // Trust gate fires first — action is denied before budget is evaluated.
    expect(decision).toBeGovernanceDenied();
    expect(decision).toRequireTrustLevel(3);
  });

  it("independent engines have isolated state", async () => {
    const engineA = createTestEngine();
    const engineB = createTestEngine();

    setTrustLevel(engineA, "shared-id", 4);
    // engineB has no entry for "shared-id" — defaults to level 0.

    const decisionA = await engineA.check({
      action: "file:read",
      context: { agentId: "shared-id" },
    });
    const decisionB = await engineB.check({
      action: "file:read",
      context: { agentId: "shared-id" },
    });

    expect(decisionA).toBeGovernancePermitted();
    expect(decisionB).toBeGovernanceDenied();
  });

  it("createTestEngine accepts config overrides", async () => {
    const engine = createTestEngine({ audit: { backend: "memory" } });

    setTrustLevel(engine, "test-agent", 3);

    const decision = await engine.check({
      action: "file:read",
      context: { agentId: "test-agent" },
    });

    expect(decision).toBeGovernancePermitted();
  });
});
