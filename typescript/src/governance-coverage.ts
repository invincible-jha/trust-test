// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 MuVeraAI Corporation

/**
 * Governance coverage metric for AumOS agent action traces.
 *
 * Governance coverage is the governance equivalent of code coverage. It answers
 * the question: "Of all the actions my agent performed, what fraction were
 * governed by each pillar?"
 *
 * The four pillars are:
 *
 * - **Trust**   — was a trust-level check performed before the action?
 * - **Budget**  — was a budget-envelope check performed before the action?
 * - **Consent** — was explicit consent verified before the action?
 * - **Audit**   — was the action outcome written to an audit log?
 *
 * Call {@link computeGovernanceCoverage} with an array of {@link ActionTrace}
 * records to obtain a {@link GovernanceCoverageReport}.
 * Use {@link formatCoverageReport} to render the report as human-readable text.
 *
 * @example
 * ```typescript
 * import {
 *   computeGovernanceCoverage,
 *   formatCoverageReport,
 * } from '@aumos/vitest-governance/governance-coverage';
 *
 * const traces: ActionTrace[] = [
 *   {
 *     actionId: 'a1',
 *     actionName: 'file:write',
 *     hasTrustCheck: true,
 *     hasBudgetCheck: true,
 *     hasConsentCheck: false,
 *     hasAuditLog: true,
 *   },
 * ];
 *
 * const report = computeGovernanceCoverage(traces);
 * console.log(formatCoverageReport(report));
 * ```
 *
 * @packageDocumentation
 */

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/**
 * Trace record for a single agent action.
 *
 * Instances are typically produced by test instrumentation, audit-log
 * parsers, or manual annotation of action sequences.
 */
export interface ActionTrace {
  /** Unique identifier for this action invocation. */
  readonly actionId: string;

  /** Human-readable name of the action, e.g. `"file:write"`. */
  readonly actionName: string;

  /** `true` if a trust-level check was performed before the action. */
  readonly hasTrustCheck: boolean;

  /** `true` if a budget-envelope check was performed before the action. */
  readonly hasBudgetCheck: boolean;

  /** `true` if explicit consent was verified before the action. */
  readonly hasConsentCheck: boolean;

  /** `true` if the action outcome was written to an audit log. */
  readonly hasAuditLog: boolean;
}

/**
 * Report of governance coverage across a set of agent action traces.
 *
 * All percentage fields are in the range [0, 100] and are rounded to one
 * decimal place.
 */
export interface GovernanceCoverageReport {
  /** Number of action traces evaluated. */
  readonly totalActions: number;

  /** Number of actions that had a trust check. */
  readonly trustChecked: number;

  /** Number of actions that had a budget check. */
  readonly budgetChecked: number;

  /** Number of actions that had a consent check. */
  readonly consentChecked: number;

  /** Number of actions that produced an audit log entry. */
  readonly auditLogged: number;

  /** Trust pillar coverage as a percentage (0–100). */
  readonly trustCoveragePct: number;

  /** Budget pillar coverage as a percentage (0–100). */
  readonly budgetCoveragePct: number;

  /** Consent pillar coverage as a percentage (0–100). */
  readonly consentCoveragePct: number;

  /** Audit pillar coverage as a percentage (0–100). */
  readonly auditCoveragePct: number;

  /**
   * Mean of the four pillar percentages (0–100).
   *
   * This is the headline figure for CI threshold checks.
   */
  readonly overallCoveragePct: number;

  /**
   * Names of actions missing a trust check **or** an audit log entry.
   *
   * Trust and audit are the two minimum safety pillars. Any action that
   * lacks either is considered uncovered regardless of budget/consent status.
   */
  readonly uncoveredActions: readonly string[];
}

// ---------------------------------------------------------------------------
// Core computation
// ---------------------------------------------------------------------------

/**
 * Round a number to one decimal place (same rounding as Python's `round(x, 1)`).
 */
function roundToOneDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

/**
 * Compute governance coverage from an array of action traces.
 *
 * Coverage is computed per-pillar (trust, budget, consent, audit) as the
 * percentage of traced actions that have the corresponding governance check.
 * Overall coverage is the unweighted mean of all four pillars.
 *
 * An action is considered *uncovered* when it lacks **either** a trust check
 * **or** an audit log entry — the two pillars that represent the minimum
 * safety bar for any governed action.
 *
 * @param traces - The action traces to analyse. May be empty.
 * @returns A {@link GovernanceCoverageReport} containing per-pillar counts,
 *          percentages, overall coverage, and the list of uncovered action names.
 *
 * @example
 * ```typescript
 * const report = computeGovernanceCoverage(traces);
 * if (report.overallCoveragePct < 80) {
 *   throw new Error(`Governance coverage ${report.overallCoveragePct}% is below the 80% threshold`);
 * }
 * ```
 */
export function computeGovernanceCoverage(
  traces: readonly ActionTrace[],
): GovernanceCoverageReport {
  const total = traces.length;

  if (total === 0) {
    return {
      totalActions: 0,
      trustChecked: 0,
      budgetChecked: 0,
      consentChecked: 0,
      auditLogged: 0,
      trustCoveragePct: 0,
      budgetCoveragePct: 0,
      consentCoveragePct: 0,
      auditCoveragePct: 0,
      overallCoveragePct: 0,
      uncoveredActions: [],
    };
  }

  const trustChecked = traces.filter((trace) => trace.hasTrustCheck).length;
  const budgetChecked = traces.filter((trace) => trace.hasBudgetCheck).length;
  const consentChecked = traces.filter((trace) => trace.hasConsentCheck).length;
  const auditLogged = traces.filter((trace) => trace.hasAuditLog).length;

  // An action is uncovered if it is missing a trust check OR an audit log.
  const uncoveredActions = traces
    .filter((trace) => !(trace.hasTrustCheck && trace.hasAuditLog))
    .map((trace) => trace.actionName);

  const trustCoveragePct = roundToOneDecimal((trustChecked / total) * 100);
  const budgetCoveragePct = roundToOneDecimal((budgetChecked / total) * 100);
  const consentCoveragePct = roundToOneDecimal((consentChecked / total) * 100);
  const auditCoveragePct = roundToOneDecimal((auditLogged / total) * 100);
  const overallCoveragePct = roundToOneDecimal(
    (trustCoveragePct + budgetCoveragePct + consentCoveragePct + auditCoveragePct) / 4,
  );

  return {
    totalActions: total,
    trustChecked,
    budgetChecked,
    consentChecked,
    auditLogged,
    trustCoveragePct,
    budgetCoveragePct,
    consentCoveragePct,
    auditCoveragePct,
    overallCoveragePct,
    uncoveredActions,
  };
}

// ---------------------------------------------------------------------------
// Report formatting
// ---------------------------------------------------------------------------

/**
 * Format a governance coverage report as a human-readable string.
 *
 * The resulting string is suitable for printing to stdout or writing to a
 * CI log. Uncovered actions are listed individually when present.
 *
 * @param report - The report produced by {@link computeGovernanceCoverage}.
 * @returns A multi-line string representation of the report.
 *
 * @example
 * ```
 * Governance Coverage Report
 * ========================================
 * Total Actions: 10
 *
 * Pillar Coverage:
 *   Trust:   100.0% (10/10)
 *   Budget:   80.0% (8/10)
 *   Consent:  70.0% (7/10)
 *   Audit:   100.0% (10/10)
 *
 * Overall Coverage: 87.5%
 *
 * Uncovered Actions (2):
 *   - data:export
 *   - network:request
 * ```
 */
export function formatCoverageReport(report: GovernanceCoverageReport): string {
  const { totalActions: total } = report;

  const pillarLine = (
    label: string,
    pct: number,
    checked: number,
  ): string => {
    // Right-pad label to 7 chars so columns align with the Python output.
    const paddedLabel = label.padEnd(7);
    const pctStr = pct.toFixed(1).padStart(5);
    return `  ${paddedLabel} ${pctStr}% (${String(checked)}/${String(total)})`;
  };

  const lines: string[] = [
    "Governance Coverage Report",
    "=".repeat(40),
    `Total Actions: ${String(total)}`,
    "",
    "Pillar Coverage:",
    pillarLine("Trust:", report.trustCoveragePct, report.trustChecked),
    pillarLine("Budget:", report.budgetCoveragePct, report.budgetChecked),
    pillarLine("Consent:", report.consentCoveragePct, report.consentChecked),
    pillarLine("Audit:", report.auditCoveragePct, report.auditLogged),
    "",
    `Overall Coverage: ${report.overallCoveragePct.toFixed(1)}%`,
  ];

  if (report.uncoveredActions.length > 0) {
    lines.push("");
    lines.push(`Uncovered Actions (${String(report.uncoveredActions.length)}):`);
    for (const actionName of report.uncoveredActions) {
      lines.push(`  - ${actionName}`);
    }
  }

  return lines.join("\n");
}
