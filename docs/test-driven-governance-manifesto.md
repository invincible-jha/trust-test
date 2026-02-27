# The Test-Driven Governance Manifesto

> **"If your governance isn't tested, it doesn't exist."**

---

Governance rules that live only in documentation, configuration files, or the minds of
engineers are not real governance. They are intentions. Real governance is governance
that has been verified — by a test suite, on every commit, against the actual engine
that runs in production.

Test-Driven Governance (TDG) is a methodology for building trustworthy AI agent systems
by treating governance requirements as the primary artifact of development. Policy rules,
trust level boundaries, budget caps, and consent requirements all begin life as failing
tests. Only after those tests are written do we implement the governance configuration
that makes them pass.

This manifesto defines the principles, workflow, and practices of TDG.

---

## The Five Principles

### 1. Governance requirements ARE test cases

Every governance requirement must be expressed as a test before it is implemented in
configuration or code.

"File uploads require elevated trust" is not a governance requirement — it is a prose
description. The requirement exists when it has a corresponding test:

```python
def test_file_upload_requires_elevated_trust(governance_engine):
    assert_trust_required(governance_engine, action="file:upload", required_level=3)
```

This principle forces governance to be precise. You cannot write a test for a vague
requirement. The act of writing the test forces you to specify exactly which trust level
is required, exactly which action identifier is being governed, and exactly what outcome
is expected. Ambiguity is resolved before any configuration is written.

This principle also makes governance reviewable. A reviewer reading a test knows exactly
what the governance system promises. They do not need to hunt through configuration
files, read documentation, or ask an engineer.

### 2. Test both sides of every boundary

Every trust level boundary must be tested from both sides: assert that level N-1 is
denied AND that level N is allowed.

Testing only the permitted side misses bugs where a policy is too permissive — where the
action is allowed at a level lower than intended. Testing only the denied side misses
bugs where a policy is too restrictive — where the action is blocked even at the correct
level.

A single boundary test that covers both sides:

```python
def test_delete_requires_trust_level_4(governance_engine):
    # Both sides tested in a single call
    assert_trust_required(governance_engine, action="file:delete", required_level=4)
```

The `assert_trust_required` helper in `pytest-aumos-governance` always performs both
checks internally. This is not optional — it is the correct way to test a trust
boundary.

The same principle applies to budget caps. A budget test must verify that a request
within the cap passes AND that a request at or above the cap is denied.

The same principle applies to consent gates. A consent test must verify that the
action is blocked without consent AND that it proceeds when consent has been recorded.

### 3. Snapshot governance decisions, not just code

Governance configurations produce deterministic outputs for a given set of inputs. Those
outputs — which actions are allowed, which are denied, what trust level each action
requires — should be captured as snapshots and compared on every configuration change.

Snapshot testing for governance means: run a canonical set of test actions through the
governance engine, record the decisions, and save the result. On subsequent runs, compare
the current decisions against the saved baseline. Any change in a governance decision is
surfaced immediately.

This catches a class of bug that test-per-requirement misses: silent regression. When a
change to one policy rule accidentally alters the decision for a different action, a
targeted test for that second action may not detect the change. A snapshot covering the
full action set will.

Governance snapshots must be human-readable. They are policy artifacts, not just test
artifacts. Storing them in version control means every governance decision change is
visible in code review, with a diff that shows exactly what changed.

### 4. Red-Green-Govern

The TDG development cycle mirrors the Red-Green-Refactor cycle of Test-Driven
Development:

**Red** — Write a failing governance test. The test describes a governance requirement
that does not yet exist in the system. Running the test suite confirms the test fails.

**Green** — Configure the governance rule that makes the test pass. Do only the minimum
configuration required to satisfy the test. Do not implement governance rules that no
test requires.

**Govern** — Verify the audit trail records the governance decision correctly, then
snapshot the current governance configuration. The snapshot is the stable baseline for
future regression detection.

This cycle ensures that every governance rule in the system exists because a test
required it. It ensures that every test in the suite corresponds to a real policy
requirement. It ensures that the audit trail is part of the acceptance criteria, not an
afterthought.

### 5. Governance coverage is a first-class metric

Code coverage tracks what percentage of code paths are exercised by tests. Governance
coverage tracks what percentage of an agent's actions are covered by governance tests.

Governance coverage is reported across four pillars:

- **Trust coverage**: what fraction of actions have a test verifying the required trust
  level?
- **Budget coverage**: what fraction of actions have a test verifying the budget
  constraint?
- **Consent coverage**: what fraction of actions that touch sensitive data have a test
  verifying the consent requirement?
- **Audit coverage**: what fraction of actions have a test verifying the audit log entry?

A codebase with high unit test coverage but low governance coverage is not a safe
codebase. Both metrics must be tracked, reported in CI, and held to a minimum standard.

---

## The TDG Cycle — Detailed Workflow

The following is the step-by-step workflow for applying TDG to a single agent action.

### Step 1 — Identify an agent action that needs governance

Every agent action that interacts with external resources, sensitive data, or
user-controlled assets requires governance. Common examples:

- File operations (read, write, delete, upload)
- Network requests (external API calls, webhooks)
- Database writes
- Calls to language models (incur cost, may process PII)
- Actions requiring user confirmation

Define the action identifier in the format `domain:verb` (e.g., `file:upload`,
`llm:call`, `pii:read`).

### Step 2 — Write a failing governance test

Before any configuration exists for this action, write a test that asserts the expected
governance decision. The test will fail because the governance rule does not yet exist.

For a trust requirement:

```python
@pytest.mark.governance
def test_file_upload_requires_trust_level_3(governance_engine):
    assert_trust_required(governance_engine, action="file:upload", required_level=3)
```

For a budget requirement:

```python
@pytest.mark.governance
def test_file_upload_budget_check(governance_engine, budget_envelope):
    budget_envelope(category="storage", limit=500.0)
    assert_budget_sufficient(governance_engine, "storage", amount=1.0)
```

For a consent requirement:

```python
@pytest.mark.governance
def test_file_upload_requires_consent(governance_engine):
    assert_consent_required(governance_engine, action="file:upload")
```

### Step 3 — Run the test suite (expect failure)

```bash
pytest --governance -m governance
```

The test will fail. This is the expected outcome at this stage. The failure confirms
that the governance rule does not yet exist in the system. If the test passes before the
rule is configured, the test is wrong.

### Step 4 — Configure the governance rule

Add the governance rule to the engine configuration. For a trust requirement, this means
specifying that `file:upload` requires trust level 3. For a budget requirement, this
means ensuring the action is wired to the correct budget category. For consent, this
means marking the action as consent-required in the policy.

Do not implement any governance rules beyond what the failing test requires. Unrequested
governance rules are not tested and therefore do not exist in the meaningful sense.

### Step 5 — Run the test suite again (expect green)

```bash
pytest --governance -m governance
```

All previously written tests must pass. If a new test passes but an existing test fails,
the new governance rule has introduced a regression. Fix the regression before
proceeding.

### Step 6 — Verify the audit trail

Add a test that verifies the governance decision is recorded in the audit log:

```python
def test_file_upload_audit_recorded(governance_engine, governed_agent):
    governed_agent(agent_id="uploader", trust_level=3)
    governance_engine.check_sync(
        action="file:upload",
        context={"agent_id": "uploader"},
    )
    assert_audit_contains(governance_engine, "file:upload", count=1)
```

The audit trail is part of the governance requirement. An action that is governed but
not recorded is only half-governed.

### Step 7 — Snapshot the governance configuration

Capture the current state of governance decisions as a named snapshot:

```python
def test_governance_snapshot(governance_engine, governance_snapshots):
    snapshot = governance_snapshots.capture(
        engine=governance_engine,
        test_actions=[
            {"action": "file:upload", "agent_id": "level-3-agent"},
            {"action": "file:upload", "agent_id": "level-2-agent"},
        ],
    )
    governance_snapshots.assert_matches(snapshot, baseline_name="file-upload-policy")
```

On the first run, the snapshot is saved as the baseline. On subsequent runs, the current
decisions are compared against the baseline. Any deviation causes the test to fail.

### Step 8 — Repeat

Return to Step 1 for the next action that requires governance.

---

## Anti-Patterns

### Testing only the happy path

A test that only asserts the action is permitted at the correct trust level is
incomplete. It does not verify that the policy enforces the boundary. Always test both
sides.

**Wrong:**
```python
def test_upload_permitted(governance_engine):
    governance_engine.trust.set_level("agent", 3, "default")
    decision = governance_engine.check_sync(
        action="file:upload",
        context={"agent_id": "agent"},
    )
    assert decision.permitted
```

**Correct:**
```python
def test_upload_requires_trust_level_3(governance_engine):
    assert_trust_required(governance_engine, action="file:upload", required_level=3)
```

### Testing governance in production

Running governance tests against a production engine, a staging engine, or any engine
with real state is incorrect. Governance tests must run against a freshly initialized
engine with known state. Any external dependency makes the test non-deterministic.

Use the `governance_engine` fixture (Python) or `createTestEngine()` (TypeScript). These
provide isolated, in-memory engines with no shared state.

### Skipping consent tests

Consent requirements are the easiest governance tests to skip because they feel
"handled elsewhere" — handled by the UI, handled by the user agreement, handled by legal.
They are not. If the governance engine does not enforce the consent requirement, no other
layer will catch it reliably.

Every action that touches user data, PII, or requires explicit user authorization must
have a consent test.

### Hardcoding trust levels in application code

Application code must never contain trust level values as magic numbers. Trust levels
belong in governance configuration. Application code checks whether an action is
permitted — it does not reason about what level is required.

**Wrong:**
```typescript
if (agent.trustLevel >= 3) {
    await uploadFile(file);
}
```

**Correct:**
```typescript
const decision = await engine.check({ action: 'file:upload', context: { agentId } });
if (decision.permitted) {
    await uploadFile(file);
}
```

### Writing governance tests after implementation

Governance tests written after the governance rules are already configured have zero
verification power for that configuration. The test was written to match the
configuration, not the requirement. Write the test first, verify it fails, then write
the configuration.

---

## Integration with CI/CD

### Pre-merge governance gate

All governance tests must pass before any branch can be merged to the main branch. Add
the governance test suite as a required CI check:

```yaml
# .github/workflows/ci.yml
- name: Run governance tests
  run: pytest --governance -m governance --tb=short
```

### Snapshot comparison on configuration changes

When a pull request modifies governance configuration, CI must run snapshot comparisons
and surface any changes as part of the review. Changes to governance decisions are not
automatically rejected — they must be reviewed explicitly.

Configure the snapshot comparison step to post a diff to the pull request comment:

```yaml
- name: Governance snapshot comparison
  run: pytest -m governance_snapshot --tb=short
  # Diff output posted to PR for review
```

### Governance coverage reporting

Generate a governance coverage report in CI and post it alongside the code coverage
report. Require a minimum governance coverage for each pillar to keep the build green:

```bash
pytest --governance --governance-coverage-report=coverage.json
```

Coverage thresholds are project-specific and should be agreed upon by the team. Once
set, they must not be lowered without explicit review and justification.

---

## Example Walkthrough — "File Upload" Action

This walkthrough demonstrates the complete TDG cycle for a `file:upload` action that
requires elevated trust and a budget check.

### Requirements (stated as prose, then as tests)

**Requirement 1**: File upload requires trust level 3.

```python
@pytest.mark.governance
def test_upload_requires_trust_level_3(governance_engine):
    assert_trust_required(governance_engine, action="file:upload", required_level=3)
```

**Requirement 2**: File uploads are charged against the `storage` budget category. A
1 MB upload must be permitted when the storage budget is sufficient.

```python
@pytest.mark.governance
def test_upload_within_storage_budget(governance_engine, budget_envelope):
    budget_envelope(category="storage", limit=100.0)
    assert_budget_sufficient(governance_engine, "storage", amount=1.0)
```

**Requirement 3**: File uploads are blocked when the storage budget is exhausted.

```python
@pytest.mark.governance
def test_upload_blocked_when_storage_exhausted(governance_engine, budget_envelope):
    budget_envelope(category="storage", limit=0.5)
    assert_budget_exceeded(governance_engine, "storage", amount=1.0)
```

**Requirement 4**: Every file upload decision is recorded in the audit log.

```python
@pytest.mark.governance
def test_upload_decision_is_audited(governance_engine, governed_agent):
    governed_agent(agent_id="uploader", trust_level=3)
    governance_engine.check_sync(
        action="file:upload",
        context={"agent_id": "uploader"},
    )
    assert_audit_contains(governance_engine, "file:upload", count=1)
```

### Step 1: Run the tests — all fail (red)

```
FAILED test_upload_requires_trust_level_3 — no policy for file:upload
FAILED test_upload_within_storage_budget — no storage envelope configured
FAILED test_upload_blocked_when_storage_exhausted — no storage envelope configured
FAILED test_upload_decision_is_audited — no audit record found
```

### Step 2: Configure the governance rule (green)

Add `file:upload` to the trust policy with `required_level: 3`. Configure the storage
budget category. Enable audit logging for the `file:` action namespace.

### Step 3: Run the tests — all pass (green)

```
PASSED test_upload_requires_trust_level_3
PASSED test_upload_within_storage_budget
PASSED test_upload_blocked_when_storage_exhausted
PASSED test_upload_decision_is_audited
```

### Step 4: Snapshot the policy

```python
@pytest.mark.governance
def test_file_upload_policy_snapshot(governance_engine, governance_snapshots):
    test_actions = [
        {"action": "file:upload", "agent_id": "level-2-agent", "description": "below threshold"},
        {"action": "file:upload", "agent_id": "level-3-agent", "description": "at threshold"},
        {"action": "file:upload", "agent_id": "level-4-agent", "description": "above threshold"},
    ]
    snapshot = governance_snapshots.capture(
        engine=governance_engine,
        test_actions=test_actions,
    )
    governance_snapshots.assert_matches(snapshot, baseline_name="file-upload-policy-v1")
```

The baseline is saved. Future changes to the `file:upload` policy will be caught by this
snapshot comparison before they reach production.

---

## Getting Started

### Python — pytest-aumos-governance

Install the plugin and write your first governance test:

```bash
pip install pytest-aumos-governance
```

See the [pytest-governance guide](./pytest-guide.md) for the full API reference,
fixture documentation, and worked examples.

### TypeScript — @aumos/vitest-governance

Install the plugin and configure the Vitest setup file:

```bash
pnpm add -D @aumos/vitest-governance
```

See the [vitest-governance guide](./vitest-guide.md) for setup instructions, custom
matchers, and worked examples.

---

## Governance Coverage Tooling

Both plugins provide governance coverage analysis via `GovernanceCoverageReport`. Import
`compute_governance_coverage` (Python) or `computeGovernanceCoverage` (TypeScript) to
generate per-pillar coverage metrics from your test action traces. See
[governance-coverage.md](./governance-coverage.md) for full documentation.

---

## Snapshot Testing

Both plugins ship a `GovernanceSnapshotManager` for capturing and comparing governance
decision snapshots across configuration changes. The Python implementation lives in
`snapshot_testing.py`. The TypeScript implementation lives in `snapshot-testing.ts`.
Both use the same JSON serialization format so snapshots are portable across languages.

---

*This document is licensed under the Creative Commons Attribution-ShareAlike 4.0
International License (CC-BY-SA-4.0). You are free to share and adapt this methodology
provided you give appropriate credit and distribute any adaptations under the same
license.*
