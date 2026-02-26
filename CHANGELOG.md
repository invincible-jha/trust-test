# Changelog

All notable changes to trust-test will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.1.0] — 2026-02-26

### Added
- `pytest-aumos-governance` Python package
  - `governance_engine` fixture providing a fresh `GovernanceEngine` per test
  - `trust_manager` and `budget_manager` convenience fixtures
  - `governed_agent` fixture factory for configurable test agents
  - `budget_envelope` fixture factory for test budget envelopes
  - `assert_trust_required` — verifies boundary enforcement at a given trust level
  - `assert_budget_sufficient` and `assert_budget_exceeded` assertions
  - `assert_consent_required`, `assert_governance_denied`, `assert_governance_permitted`
  - `assert_audit_contains` — verifies audit log entries for an action
  - `GovernanceDecisionMatcher` fluent matcher via `expect_decision()`
  - `--governance` CLI flag and `governance` pytest marker
- `@aumos/vitest-governance` TypeScript package
  - `governanceMatchers()` — custom Vitest matchers for `GovernanceDecision`
    - `toBeGovernancePermitted()`
    - `toBeGovernanceDenied()`
    - `toRequireTrustLevel(level)`
    - `toHaveBudgetAvailable(amount)`
  - `createTestEngine()` helper
  - `setTrustLevel()` and `createBudget()` helpers
- Documentation: `docs/pytest-guide.md` and `docs/vitest-guide.md`
- Apache 2.0 license

[Unreleased]: https://github.com/muveraai/aumos-oss/compare/trust-test-v0.1.0...HEAD
[0.1.0]: https://github.com/muveraai/aumos-oss/releases/tag/trust-test-v0.1.0
