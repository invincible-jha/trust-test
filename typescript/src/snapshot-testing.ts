// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * Governance snapshot testing for AumOS governance engines.
 *
 * Snapshot testing captures governance decisions for a canonical set of test
 * actions and saves them as a JSON baseline. On subsequent runs the current
 * decisions are compared against the baseline, and any change causes the test
 * to fail.
 *
 * This approach catches silent regressions where a change to one policy rule
 * accidentally alters the decision for a different action — a class of bug
 * that per-requirement tests may not detect.
 *
 * The JSON serialization format is compatible with the Python
 * `snapshot_testing.py` module so that snapshots can be shared and compared
 * across language boundaries.
 *
 * @example
 * ```typescript
 * import { createSnapshotManager } from '@aumos/vitest-governance/snapshot-testing';
 * import { createTestEngine } from '@aumos/vitest-governance';
 *
 * const engine = createTestEngine();
 * const manager = createSnapshotManager('.governance-snapshots');
 *
 * const snapshot = manager.capture(engine, [
 *   { action: 'file:upload', agentId: 'level-2-agent', description: 'below threshold' },
 *   { action: 'file:upload', agentId: 'level-3-agent', description: 'at threshold' },
 * ]);
 *
 * manager.assertMatches(snapshot, 'file-upload-policy');
 * ```
 *
 * @packageDocumentation
 */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/**
 * Input descriptor for a single action to evaluate during snapshot capture.
 */
export interface TestAction {
  /** The action string to evaluate, e.g. `"file:upload"`. */
  readonly action: string;
  /** The agent identifier to use for the check. */
  readonly agentId: string;
  /** Human-readable description of what is being tested. Optional. */
  readonly description?: string;
  /** Resource being accessed. Optional — defaults to empty string. */
  readonly resource?: string;
  /** Budget amount to record in the decision. Optional. */
  readonly budgetRequired?: number;
}

/**
 * A single governance decision captured during a snapshot run.
 *
 * All properties are `readonly` to enforce immutability after capture.
 * The shape matches the Python `SnapshotDecision` dataclass for
 * cross-language compatibility.
 */
export interface SnapshotDecision {
  /** Human-readable description of what was being tested. */
  readonly actionDescription: string;
  /** The agent identifier used for the decision check. */
  readonly agentId: string;
  /** The action string evaluated, e.g. `"file:upload"`. */
  readonly actionKind: string;
  /** The resource being accessed, or an empty string when not applicable. */
  readonly resource: string;
  /** The trust level the policy requires for this action. */
  readonly trustLevelRequired: number;
  /** Budget amount required, or `null` when no budget check applied. */
  readonly budgetRequired: number | null;
  /** `true` if the action requires explicit consent. */
  readonly consentRequired: boolean;
  /** The outcome of the governance check. */
  readonly expectedOutcome: "allowed" | "denied" | "requires_consent";
  /** The denial reason from the engine, or `null` when the action was allowed. */
  readonly denialReason: string | null;
}

/**
 * Frozen snapshot of governance decisions for a set of test actions.
 *
 * All properties are `readonly` to enforce immutability after capture.
 */
export interface GovernanceSnapshot {
  /** Unique identifier for this snapshot instance. */
  readonly snapshotId: string;
  /** ISO 8601 timestamp of when the snapshot was captured. */
  readonly createdAt: string;
  /** SHA-256 hex digest of the serialized engine configuration. */
  readonly engineConfigHash: string;
  /** Ordered list of captured governance decisions. */
  readonly decisions: readonly SnapshotDecision[];
}

/**
 * Result of comparing two governance snapshots.
 *
 * All properties are `readonly` to enforce immutability.
 */
export interface SnapshotDiff {
  /**
   * `true` when the current snapshot is identical to the baseline — no
   * additions, removals, or changes.
   */
  readonly matches: boolean;
  /** Decisions present in `current` but not in `baseline`. */
  readonly added: readonly SnapshotDecision[];
  /** Decisions present in `baseline` but not in `current`. */
  readonly removed: readonly SnapshotDecision[];
  /**
   * Pairs of `[baselineDecision, currentDecision]` for decisions whose
   * outcome or metadata changed between snapshots.
   */
  readonly changed: readonly [SnapshotDecision, SnapshotDecision][];
}

// ---------------------------------------------------------------------------
// JSON wire format (snake_case to match Python output)
// ---------------------------------------------------------------------------

interface SnapshotDecisionJson {
  action_description: string;
  agent_id: string;
  action_kind: string;
  resource: string;
  trust_level_required: number;
  budget_required: number | null;
  consent_required: boolean;
  expected_outcome: "allowed" | "denied" | "requires_consent";
  denial_reason: string | null;
}

interface GovernanceSnapshotJson {
  snapshot_id: string;
  created_at: string;
  engine_config_hash: string;
  decisions: SnapshotDecisionJson[];
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function hashEngineConfig(engine: unknown): string {
  let configText: string;

  if (
    engine !== null &&
    typeof engine === "object" &&
    "config" in engine
  ) {
    try {
      configText = JSON.stringify(
        (engine as { config: unknown }).config,
        (_key, value: unknown) => (typeof value === "bigint" ? String(value) : value),
      );
    } catch {
      configText = String((engine as { config: unknown }).config);
    }
  } else {
    // Fallback: use the constructor name so the hash still changes when the
    // engine type changes.
    const constructorName =
      engine !== null && typeof engine === "object"
        ? (engine as object).constructor?.name ?? "UnknownEngine"
        : "UnknownEngine";
    configText = constructorName;
  }

  return createHash("sha256").update(configText, "utf8").digest("hex");
}

function actionKey(decision: SnapshotDecision): string {
  return `${decision.actionKind}::${decision.agentId}`;
}

function generateSnapshotId(
  decisions: readonly SnapshotDecision[],
  createdAt: string,
): string {
  const content = JSON.stringify(
    decisions.map((d) => decisionToJson(d)),
  );
  const contentHash = createHash("sha256")
    .update(content, "utf8")
    .digest("hex")
    .slice(0, 8);
  // Produce a timestamp prefix compatible with the Python implementation
  const timestampPrefix = createdAt
    .replace(/:/g, "")
    .replace(/-/g, "")
    .replace("T", "-")
    .slice(0, 15);
  return `snapshot-${timestampPrefix}-${contentHash}`;
}

function decisionToJson(decision: SnapshotDecision): SnapshotDecisionJson {
  return {
    action_description: decision.actionDescription,
    agent_id: decision.agentId,
    action_kind: decision.actionKind,
    resource: decision.resource,
    trust_level_required: decision.trustLevelRequired,
    budget_required: decision.budgetRequired,
    consent_required: decision.consentRequired,
    expected_outcome: decision.expectedOutcome,
    denial_reason: decision.denialReason,
  };
}

function decisionFromJson(json: SnapshotDecisionJson): SnapshotDecision {
  return {
    actionDescription: json.action_description,
    agentId: json.agent_id,
    actionKind: json.action_kind,
    resource: json.resource,
    trustLevelRequired: json.trust_level_required,
    budgetRequired: json.budget_required,
    consentRequired: json.consent_required,
    expectedOutcome: json.expected_outcome,
    denialReason: json.denial_reason,
  };
}

function snapshotToJson(snapshot: GovernanceSnapshot): GovernanceSnapshotJson {
  return {
    snapshot_id: snapshot.snapshotId,
    created_at: snapshot.createdAt,
    engine_config_hash: snapshot.engineConfigHash,
    decisions: snapshot.decisions.map(decisionToJson),
  };
}

function snapshotFromJson(json: GovernanceSnapshotJson): GovernanceSnapshot {
  return {
    snapshotId: json.snapshot_id,
    createdAt: json.created_at,
    engineConfigHash: json.engine_config_hash,
    decisions: json.decisions.map(decisionFromJson),
  };
}

function evaluateAction(
  engine: unknown,
  testAction: TestAction,
): SnapshotDecision {
  const actionKind = testAction.action;
  const agentId = testAction.agentId;
  const description =
    testAction.description ?? `${actionKind} as ${agentId}`;
  const resource = testAction.resource ?? "";
  const budgetRequired = testAction.budgetRequired ?? null;

  // Engine is typed as `unknown` — callers narrow to their concrete type.
  // We use duck-typing to access the check result.
  const context: Record<string, unknown> = { agentId };
  if (resource) {
    context["resource"] = resource;
  }

  const engineObj = engine as {
    checkSync?: (opts: { action: string; context: Record<string, unknown> }) => unknown;
  };

  if (typeof engineObj.checkSync !== "function") {
    throw new Error(
      `Engine does not expose a checkSync method. ` +
      `Received: ${JSON.stringify(Object.keys(engineObj))}`,
    );
  }

  const decision = engineObj.checkSync({ action: actionKind, context });

  const decisionObj = decision as {
    permitted?: boolean;
    reason?: string;
    trust?: { requiredLevel?: number };
    consent?: { permitted?: boolean };
  };

  const permitted = decisionObj.permitted === true;
  const consentSub = decisionObj.consent ?? null;
  const consentDenied =
    consentSub !== null && consentSub.permitted === false;

  let expectedOutcome: "allowed" | "denied" | "requires_consent";
  if (!permitted && consentDenied) {
    expectedOutcome = "requires_consent";
  } else if (permitted) {
    expectedOutcome = "allowed";
  } else {
    expectedOutcome = "denied";
  }

  const trustLevelRequired =
    decisionObj.trust?.requiredLevel ?? 0;

  const consentRequired =
    consentDenied ||
    (consentSub !== null && consentSub.permitted === false);

  const denialReason =
    !permitted && typeof decisionObj.reason === "string"
      ? decisionObj.reason
      : null;

  return {
    actionDescription: description,
    agentId,
    actionKind,
    resource,
    trustLevelRequired,
    budgetRequired,
    consentRequired,
    expectedOutcome,
    denialReason,
  };
}

function decisionsAreEqual(
  a: SnapshotDecision,
  b: SnapshotDecision,
): boolean {
  return (
    a.actionDescription === b.actionDescription &&
    a.agentId === b.agentId &&
    a.actionKind === b.actionKind &&
    a.resource === b.resource &&
    a.trustLevelRequired === b.trustLevelRequired &&
    a.budgetRequired === b.budgetRequired &&
    a.consentRequired === b.consentRequired &&
    a.expectedOutcome === b.expectedOutcome &&
    a.denialReason === b.denialReason
  );
}

// ---------------------------------------------------------------------------
// Diff summary formatting
// ---------------------------------------------------------------------------

/**
 * Return a human-readable summary of a `SnapshotDiff`.
 *
 * @param diff - The diff to summarise.
 * @returns A multi-line string describing what changed, or a confirmation
 *   that the snapshots match if no changes were found.
 */
export function formatSnapshotDiff(diff: SnapshotDiff): string {
  if (diff.matches) {
    return "Snapshots match — no governance decisions changed.";
  }

  const lines: string[] = ["Governance snapshot mismatch detected:"];

  if (diff.added.length > 0) {
    lines.push(`\n  Added (${diff.added.length} decision(s)):`);
    for (const decision of diff.added) {
      lines.push(
        `    + [${decision.expectedOutcome.toUpperCase()}] ` +
        `${decision.actionKind} (agent=${decision.agentId})`,
      );
    }
  }

  if (diff.removed.length > 0) {
    lines.push(`\n  Removed (${diff.removed.length} decision(s)):`);
    for (const decision of diff.removed) {
      lines.push(
        `    - [${decision.expectedOutcome.toUpperCase()}] ` +
        `${decision.actionKind} (agent=${decision.agentId})`,
      );
    }
  }

  if (diff.changed.length > 0) {
    lines.push(`\n  Changed (${diff.changed.length} decision(s)):`);
    for (const [baselineDecision, currentDecision] of diff.changed) {
      lines.push(
        `    ~ ${baselineDecision.actionKind} ` +
        `(agent=${baselineDecision.agentId}):`,
      );
      if (baselineDecision.expectedOutcome !== currentDecision.expectedOutcome) {
        lines.push(
          `      outcome: ${JSON.stringify(baselineDecision.expectedOutcome)} ` +
          `-> ${JSON.stringify(currentDecision.expectedOutcome)}`,
        );
      }
      if (baselineDecision.trustLevelRequired !== currentDecision.trustLevelRequired) {
        lines.push(
          `      trustLevelRequired: ${baselineDecision.trustLevelRequired} ` +
          `-> ${currentDecision.trustLevelRequired}`,
        );
      }
      if (baselineDecision.denialReason !== currentDecision.denialReason) {
        lines.push(
          `      denialReason: ${JSON.stringify(baselineDecision.denialReason)} ` +
          `-> ${JSON.stringify(currentDecision.denialReason)}`,
        );
      }
      if (baselineDecision.consentRequired !== currentDecision.consentRequired) {
        lines.push(
          `      consentRequired: ${baselineDecision.consentRequired} ` +
          `-> ${currentDecision.consentRequired}`,
        );
      }
    }
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Core class
// ---------------------------------------------------------------------------

/**
 * Manages governance decision snapshots for regression testing.
 *
 * Snapshots are stored as JSON files in the directory provided at
 * construction time. Each snapshot file is named `<name>.snapshot.json`.
 * The file format matches the Python `GovernanceSnapshotManager` output
 * for cross-language compatibility.
 *
 * All snapshot objects produced by this manager satisfy the `GovernanceSnapshot`
 * interface — all properties are `readonly`.
 *
 * @example
 * ```typescript
 * const manager = new GovernanceSnapshotManager('.governance-snapshots');
 * const snapshot = manager.capture(engine, testActions);
 * manager.save(snapshot, 'my-policy');
 * manager.assertMatches(snapshot, 'my-policy');
 * ```
 */
export class GovernanceSnapshotManager {
  private readonly snapshotDir: string;

  /**
   * @param snapshotDir - Directory where snapshot files are stored.
   *   Created automatically if it does not exist.
   */
  constructor(snapshotDir: string) {
    this.snapshotDir = resolve(snapshotDir);
    if (!existsSync(this.snapshotDir)) {
      mkdirSync(this.snapshotDir, { recursive: true });
    }
  }

  /**
   * Run all test actions through the engine and capture the decisions.
   *
   * Each entry in `testActions` must have at minimum `action` and `agentId`
   * set. The remaining fields are optional.
   *
   * The engine is typed as `unknown` — callers narrow to their concrete
   * engine type. The engine must expose a `checkSync` method that accepts
   * `{ action, context }` and returns a decision object.
   *
   * @param engine - A governance engine instance.
   * @param testActions - Actions to evaluate.
   * @returns An immutable `GovernanceSnapshot` containing the recorded decisions.
   */
  public capture(
    engine: unknown,
    testActions: readonly TestAction[],
  ): GovernanceSnapshot {
    const createdAt = new Date().toISOString();
    const engineConfigHash = hashEngineConfig(engine);

    const decisions: SnapshotDecision[] = testActions.map((action) =>
      evaluateAction(engine, action),
    );

    const snapshotId = generateSnapshotId(decisions, createdAt);

    return {
      snapshotId,
      createdAt,
      engineConfigHash,
      decisions,
    };
  }

  /**
   * Save a snapshot to a JSON file in the snapshot directory.
   *
   * The file is written to `<snapshotDir>/<name>.snapshot.json`.
   * Any existing file with the same name is overwritten.
   *
   * @param snapshot - The snapshot to persist.
   * @param name - A short name for this snapshot, e.g. `"file-upload-policy"`.
   * @returns The absolute path to the written file.
   */
  public save(snapshot: GovernanceSnapshot, name: string): string {
    const filePath = join(this.snapshotDir, `${name}.snapshot.json`);
    const payload = snapshotToJson(snapshot);
    writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf8");
    return resolve(filePath);
  }

  /**
   * Load a snapshot from a JSON file in the snapshot directory.
   *
   * @param name - The name used when the snapshot was saved.
   * @returns The deserialized `GovernanceSnapshot`.
   * @throws `Error` if no snapshot file with the given name exists or if
   *   the file content cannot be parsed as a valid snapshot.
   */
  public load(name: string): GovernanceSnapshot {
    const filePath = join(this.snapshotDir, `${name}.snapshot.json`);
    if (!existsSync(filePath)) {
      throw new Error(
        `No governance snapshot found for name '${name}'. ` +
        `Expected file: ${filePath}. ` +
        `Run capture() and save() first to create the baseline.`,
      );
    }
    let raw: string;
    try {
      raw = readFileSync(filePath, "utf8");
    } catch (cause) {
      throw new Error(
        `Failed to read governance snapshot '${name}' from ${filePath}: ${String(cause)}`,
        { cause },
      );
    }
    let data: GovernanceSnapshotJson;
    try {
      data = JSON.parse(raw) as GovernanceSnapshotJson;
    } catch (cause) {
      throw new Error(
        `Failed to parse governance snapshot '${name}' from ${filePath}: ${String(cause)}`,
        { cause },
      );
    }
    return snapshotFromJson(data);
  }

  /**
   * Compare two snapshots and return a structured diff.
   *
   * Decisions are matched by their `(actionKind, agentId)` key. A decision
   * is considered *changed* when its key is present in both snapshots but any
   * field value differs.
   *
   * @param current - The snapshot taken from the current engine state.
   * @param baseline - The previously saved baseline snapshot.
   * @returns A `SnapshotDiff` describing additions, removals, and changes.
   */
  public compare(
    current: GovernanceSnapshot,
    baseline: GovernanceSnapshot,
  ): SnapshotDiff {
    const baselineByKey = new Map<string, SnapshotDecision>(
      baseline.decisions.map((d) => [actionKey(d), d]),
    );
    const currentByKey = new Map<string, SnapshotDecision>(
      current.decisions.map((d) => [actionKey(d), d]),
    );

    const baselineKeys = new Set(baselineByKey.keys());
    const currentKeys = new Set(currentByKey.keys());

    const added: SnapshotDecision[] = [...currentKeys]
      .filter((k) => !baselineKeys.has(k))
      .sort()
      .map((k) => currentByKey.get(k) as SnapshotDecision);

    const removed: SnapshotDecision[] = [...baselineKeys]
      .filter((k) => !currentKeys.has(k))
      .sort()
      .map((k) => baselineByKey.get(k) as SnapshotDecision);

    const changed: [SnapshotDecision, SnapshotDecision][] = [...baselineKeys]
      .filter((k) => currentKeys.has(k))
      .sort()
      .flatMap((k): [SnapshotDecision, SnapshotDecision][] => {
        const baselineDecision = baselineByKey.get(k) as SnapshotDecision;
        const currentDecision = currentByKey.get(k) as SnapshotDecision;
        return decisionsAreEqual(baselineDecision, currentDecision)
          ? []
          : [[baselineDecision, currentDecision]];
      });

    const matches = added.length === 0 && removed.length === 0 && changed.length === 0;

    return { matches, added, removed, changed };
  }

  /**
   * Assert that the current snapshot matches the saved baseline.
   *
   * If no baseline exists under `baselineName`, the current snapshot is saved
   * as the new baseline and the assertion passes. This allows the first run to
   * establish the baseline automatically.
   *
   * On subsequent runs the current snapshot is compared against the saved
   * baseline. Any difference causes an `Error` with a detailed summary of
   * what changed.
   *
   * @param current - The snapshot taken from the current engine state.
   * @param baselineName - The name of the baseline to compare against.
   * @throws `Error` if the current snapshot differs from the baseline.
   */
  public assertMatches(
    current: GovernanceSnapshot,
    baselineName: string,
  ): void {
    const filePath = join(this.snapshotDir, `${baselineName}.snapshot.json`);

    if (!existsSync(filePath)) {
      // First run — save as baseline, assertion passes.
      this.save(current, baselineName);
      return;
    }

    const baseline = this.load(baselineName);
    const diff = this.compare(current, baseline);

    if (!diff.matches) {
      throw new Error(
        `Governance snapshot '${baselineName}' has changed.\n\n` +
        `${formatSnapshotDiff(diff)}\n\n` +
        `If this change is intentional, delete the baseline file and re-run ` +
        `to establish a new baseline:\n` +
        `  ${filePath}`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Factory helper
// ---------------------------------------------------------------------------

/**
 * Create a `GovernanceSnapshotManager` with a sensible default directory.
 *
 * When `dir` is omitted the manager uses `.governance-snapshots` relative to
 * the current working directory. Pass an absolute or relative path to store
 * snapshots in a different location.
 *
 * @param dir - Optional path to the snapshot directory.
 * @returns A new `GovernanceSnapshotManager` instance.
 *
 * @example
 * ```typescript
 * // Default location
 * const manager = createSnapshotManager();
 *
 * // Project-specific location
 * const manager = createSnapshotManager('tests/.governance-snapshots');
 * ```
 */
export function createSnapshotManager(dir?: string): GovernanceSnapshotManager {
  return new GovernanceSnapshotManager(dir ?? ".governance-snapshots");
}
