# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""Governance snapshot testing for AumOS governance engines.

Snapshot testing captures governance decisions for a canonical set of test
actions and saves them as a JSON baseline. On subsequent runs the current
decisions are compared against the baseline, and any change causes the test
to fail.

This approach catches silent regressions where a change to one policy rule
accidentally alters the decision for a different action — a class of bug that
per-requirement tests may not detect.

Usage
-----
::

    from snapshot_testing import GovernanceSnapshotManager
    import pytest

    @pytest.fixture
    def governance_snapshots(tmp_path):
        return GovernanceSnapshotManager(tmp_path)

    def test_upload_policy_snapshot(governance_engine, governance_snapshots):
        test_actions = [
            {
                "action": "file:upload",
                "agent_id": "level-2-agent",
                "description": "below required trust",
            },
            {
                "action": "file:upload",
                "agent_id": "level-3-agent",
                "description": "at required trust",
            },
        ]
        snapshot = governance_snapshots.capture(
            engine=governance_engine,
            test_actions=test_actions,
        )
        governance_snapshots.assert_matches(snapshot, baseline_name="file-upload-policy")

Design notes
------------
- All public types are frozen dataclasses (immutable after construction).
- The engine configuration is hashed with SHA-256 to detect configuration
  drift between snapshot captures.
- Snapshots are stored as human-readable JSON files so that diffs are
  visible in version control and code review.
- This module has no dependency on pytest internals — it is a standalone
  utility class. The ``governance_snapshots`` pytest fixture at the bottom
  of this file is provided for convenience.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SnapshotDecision:
    """A single governance decision captured during a snapshot run.

    Attributes:
        action_description: Human-readable description of what was being tested,
            e.g. ``"below required trust"``.
        agent_id: The agent identifier used for the decision check.
        action_kind: The action string evaluated, e.g. ``"file:upload"``.
        resource: The resource being accessed, or an empty string when not
            applicable.
        trust_level_required: The trust level the policy requires for this action.
        budget_required: The budget amount required, or ``None`` when no budget
            check was part of this decision.
        consent_required: ``True`` if the action requires explicit consent.
        expected_outcome: One of ``"allowed"``, ``"denied"``, or
            ``"requires_consent"``.
        denial_reason: The reason string from the engine when the action was
            denied, or ``None`` when the action was allowed.
    """

    action_description: str
    agent_id: str
    action_kind: str
    resource: str
    trust_level_required: int
    budget_required: float | None
    consent_required: bool
    expected_outcome: str  # "allowed" | "denied" | "requires_consent"
    denial_reason: str | None


@dataclass(frozen=True)
class GovernanceSnapshot:
    """Frozen snapshot of governance decisions for a set of test actions.

    Attributes:
        snapshot_id: A unique identifier for this snapshot instance, derived
            from the creation timestamp and a short hash of the decisions.
        created_at: ISO 8601 timestamp of when the snapshot was captured.
        engine_config_hash: SHA-256 hex digest of the serialized engine
            configuration. Changes when the engine's policy configuration
            is modified.
        decisions: Ordered list of captured governance decisions.
    """

    snapshot_id: str
    created_at: str  # ISO 8601
    engine_config_hash: str  # SHA-256 hex digest of serialized config
    decisions: list[SnapshotDecision]


@dataclass(frozen=True)
class SnapshotDiff:
    """Result of comparing two governance snapshots.

    Attributes:
        matches: ``True`` when the current snapshot is identical to the
            baseline (no additions, removals, or changes).
        added: Decisions present in ``current`` but not in ``baseline``.
        removed: Decisions present in ``baseline`` but not in ``current``.
        changed: Pairs of ``(baseline_decision, current_decision)`` for
            decisions whose outcome or metadata changed between snapshots.
    """

    matches: bool
    added: list[SnapshotDecision]
    removed: list[SnapshotDecision]
    changed: list[tuple[SnapshotDecision, SnapshotDecision]]

    def summary(self) -> str:
        """Return a human-readable summary of the differences.

        Returns:
            A multi-line string describing what changed, or a confirmation
            that the snapshots match if no changes were found.
        """
        if self.matches:
            return "Snapshots match — no governance decisions changed."

        lines: list[str] = ["Governance snapshot mismatch detected:"]

        if self.added:
            lines.append(f"\n  Added ({len(self.added)} decision(s)):")
            for decision in self.added:
                lines.append(
                    f"    + [{decision.expected_outcome.upper()}] "
                    f"{decision.action_kind} (agent={decision.agent_id})"
                )

        if self.removed:
            lines.append(f"\n  Removed ({len(self.removed)} decision(s)):")
            for decision in self.removed:
                lines.append(
                    f"    - [{decision.expected_outcome.upper()}] "
                    f"{decision.action_kind} (agent={decision.agent_id})"
                )

        if self.changed:
            lines.append(f"\n  Changed ({len(self.changed)} decision(s)):")
            for baseline_decision, current_decision in self.changed:
                lines.append(
                    f"    ~ {baseline_decision.action_kind} "
                    f"(agent={baseline_decision.agent_id}):"
                )
                if baseline_decision.expected_outcome != current_decision.expected_outcome:
                    lines.append(
                        f"      outcome: {baseline_decision.expected_outcome!r} "
                        f"-> {current_decision.expected_outcome!r}"
                    )
                if baseline_decision.trust_level_required != current_decision.trust_level_required:
                    lines.append(
                        f"      trust_level_required: "
                        f"{baseline_decision.trust_level_required} "
                        f"-> {current_decision.trust_level_required}"
                    )
                if baseline_decision.denial_reason != current_decision.denial_reason:
                    lines.append(
                        f"      denial_reason: {baseline_decision.denial_reason!r} "
                        f"-> {current_decision.denial_reason!r}"
                    )
                if baseline_decision.consent_required != current_decision.consent_required:
                    lines.append(
                        f"      consent_required: {baseline_decision.consent_required} "
                        f"-> {current_decision.consent_required}"
                    )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_engine_config(engine: Any) -> str:
    """Compute a SHA-256 hash of the engine's serialized configuration.

    The hash is used to detect configuration drift between snapshot captures.
    When the hash changes, the snapshot was taken against a different policy
    configuration.

    Args:
        engine: A governance engine instance. The function inspects
            ``engine.config`` if available, falling back to the engine's
            class name and id to produce a stable-but-distinct value.

    Returns:
        A 64-character lowercase hex SHA-256 digest.
    """
    config_object = getattr(engine, "config", None)
    if config_object is not None:
        try:
            config_text = json.dumps(
                config_object.__dict__ if hasattr(config_object, "__dict__") else str(config_object),
                sort_keys=True,
                default=str,
            )
        except (TypeError, ValueError):
            config_text = str(config_object)
    else:
        # Fallback: use the engine class name to produce a deterministic string
        # that still changes when the engine type changes.
        config_text = f"{type(engine).__module__}.{type(engine).__qualname__}"

    return hashlib.sha256(config_text.encode("utf-8")).hexdigest()


def _action_key(decision: SnapshotDecision) -> str:
    """Return a string key that uniquely identifies a decision within a snapshot.

    Args:
        decision: The snapshot decision to key.

    Returns:
        A string combining action_kind and agent_id.
    """
    return f"{decision.action_kind}::{decision.agent_id}"


def _evaluate_action(engine: Any, test_action: dict[str, Any]) -> SnapshotDecision:
    """Evaluate a single test action against the engine and return a decision record.

    Args:
        engine: A governance engine instance with a ``check_sync`` method.
        test_action: A dict with keys:
            - ``action`` (str): The action string to evaluate.
            - ``agent_id`` (str): The agent to evaluate as.
            - ``description`` (str, optional): Human-readable description.
            - ``resource`` (str, optional): Resource being accessed.
            - ``budget_required`` (float, optional): Budget amount to check.

    Returns:
        A ``SnapshotDecision`` capturing the engine's response.

    Raises:
        KeyError: If ``test_action`` is missing the required ``action`` or
            ``agent_id`` keys.
    """
    action_kind: str = test_action["action"]
    agent_id: str = test_action["agent_id"]
    description: str = test_action.get("description", f"{action_kind} as {agent_id}")
    resource: str = test_action.get("resource", "")
    budget_required: float | None = test_action.get("budget_required", None)

    context: dict[str, Any] = {"agent_id": agent_id}
    if resource:
        context["resource"] = resource

    decision = engine.check_sync(action=action_kind, context=context)

    # Determine expected_outcome
    consent_sub = getattr(decision, "consent", None)
    consent_denied = consent_sub is not None and not consent_sub.permitted
    if not decision.permitted and consent_denied:
        expected_outcome = "requires_consent"
    elif decision.permitted:
        expected_outcome = "allowed"
    else:
        expected_outcome = "denied"

    # Extract trust metadata
    trust_sub = getattr(decision, "trust", None)
    trust_level_required: int = (
        getattr(trust_sub, "required_level", 0) if trust_sub is not None else 0
    )

    # Determine consent_required
    consent_required: bool = consent_denied or (
        consent_sub is not None and not getattr(consent_sub, "permitted", True)
    )

    # Denial reason
    denial_reason: str | None = None
    if not decision.permitted:
        denial_reason = getattr(decision, "reason", None)

    return SnapshotDecision(
        action_description=description,
        agent_id=agent_id,
        action_kind=action_kind,
        resource=resource,
        trust_level_required=trust_level_required,
        budget_required=budget_required,
        consent_required=consent_required,
        expected_outcome=expected_outcome,
        denial_reason=denial_reason,
    )


def _snapshot_to_dict(snapshot: GovernanceSnapshot) -> dict[str, Any]:
    """Serialize a GovernanceSnapshot to a JSON-compatible dict.

    Args:
        snapshot: The snapshot to serialize.

    Returns:
        A plain dict suitable for ``json.dumps``.
    """
    return {
        "snapshot_id": snapshot.snapshot_id,
        "created_at": snapshot.created_at,
        "engine_config_hash": snapshot.engine_config_hash,
        "decisions": [asdict(d) for d in snapshot.decisions],
    }


def _snapshot_from_dict(data: dict[str, Any]) -> GovernanceSnapshot:
    """Deserialize a GovernanceSnapshot from a JSON-compatible dict.

    Args:
        data: A dict as produced by ``_snapshot_to_dict``.

    Returns:
        A ``GovernanceSnapshot`` instance.
    """
    decisions = [SnapshotDecision(**d) for d in data["decisions"]]
    return GovernanceSnapshot(
        snapshot_id=data["snapshot_id"],
        created_at=data["created_at"],
        engine_config_hash=data["engine_config_hash"],
        decisions=decisions,
    )


def _generate_snapshot_id(decisions: list[SnapshotDecision], created_at: str) -> str:
    """Derive a snapshot identifier from its content and timestamp.

    Args:
        decisions: The list of decisions in the snapshot.
        created_at: The ISO 8601 creation timestamp.

    Returns:
        A string in the form ``snapshot-<timestamp-prefix>-<content-hash-8>``.
    """
    content = json.dumps(
        [asdict(d) for d in decisions],
        sort_keys=True,
    )
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    timestamp_prefix = created_at.replace(":", "").replace("-", "").replace("T", "-")[:15]
    return f"snapshot-{timestamp_prefix}-{content_hash}"


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------


class GovernanceSnapshotManager:
    """Manages governance decision snapshots for regression testing.

    Snapshots are stored as JSON files in the directory provided at
    construction time. Each snapshot file is named ``<name>.snapshot.json``.

    All snapshot objects produced by this manager are frozen dataclasses —
    they cannot be modified after capture.

    Args:
        snapshot_dir: The directory in which snapshot files are stored.
            Created automatically if it does not exist.

    Example::

        manager = GovernanceSnapshotManager(Path(".governance-snapshots"))
        snapshot = manager.capture(engine, test_actions)
        manager.save(snapshot, "my-policy")
        manager.assert_matches(snapshot, "my-policy")
    """

    def __init__(self, snapshot_dir: Path) -> None:
        self._snapshot_dir = snapshot_dir
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        engine: Any,
        test_actions: list[dict[str, Any]],
    ) -> GovernanceSnapshot:
        """Run all test actions through the engine and capture the decisions.

        Each entry in ``test_actions`` must contain at minimum ``action`` and
        ``agent_id`` keys. Optional keys: ``description``, ``resource``,
        ``budget_required``.

        Args:
            engine: A governance engine instance with a ``check_sync`` method.
            test_actions: A list of action dicts to evaluate.

        Returns:
            An immutable ``GovernanceSnapshot`` containing the recorded decisions.

        Raises:
            KeyError: If any entry in ``test_actions`` is missing ``action``
                or ``agent_id``.
        """
        created_at = datetime.now(tz=timezone.utc).isoformat()
        engine_config_hash = _hash_engine_config(engine)

        decisions: list[SnapshotDecision] = [
            _evaluate_action(engine, action) for action in test_actions
        ]

        snapshot_id = _generate_snapshot_id(decisions, created_at)

        return GovernanceSnapshot(
            snapshot_id=snapshot_id,
            created_at=created_at,
            engine_config_hash=engine_config_hash,
            decisions=decisions,
        )

    def save(self, snapshot: GovernanceSnapshot, name: str) -> Path:
        """Save a snapshot to a JSON file in the snapshot directory.

        The file is written to ``<snapshot_dir>/<name>.snapshot.json``.
        Any existing file with the same name is overwritten.

        Args:
            snapshot: The snapshot to persist.
            name: A short name for this snapshot, e.g. ``"file-upload-policy"``.

        Returns:
            The absolute path to the written file.
        """
        file_path = self._snapshot_dir / f"{name}.snapshot.json"
        payload = _snapshot_to_dict(snapshot)
        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return file_path.resolve()

    def load(self, name: str) -> GovernanceSnapshot:
        """Load a snapshot from a JSON file in the snapshot directory.

        Args:
            name: The name used when the snapshot was saved, e.g.
                ``"file-upload-policy"``.

        Returns:
            The deserialized ``GovernanceSnapshot``.

        Raises:
            FileNotFoundError: If no snapshot file with the given name exists.
            ValueError: If the file content cannot be parsed as a valid snapshot.
        """
        file_path = self._snapshot_dir / f"{name}.snapshot.json"
        if not file_path.exists():
            raise FileNotFoundError(
                f"No governance snapshot found for name '{name}'. "
                f"Expected file: {file_path}. "
                f"Run capture() and save() first to create the baseline."
            )
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return _snapshot_from_dict(data)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Failed to deserialize governance snapshot '{name}' "
                f"from {file_path}: {exc}"
            ) from exc

    def compare(
        self,
        current: GovernanceSnapshot,
        baseline: GovernanceSnapshot,
    ) -> SnapshotDiff:
        """Compare two snapshots and return a structured diff.

        Decisions are matched by their ``(action_kind, agent_id)`` key. A
        decision is considered *changed* when its key is present in both
        snapshots but any field value differs.

        Args:
            current: The snapshot taken from the current engine state.
            baseline: The previously saved baseline snapshot.

        Returns:
            A ``SnapshotDiff`` describing additions, removals, and changes.
        """
        baseline_by_key: dict[str, SnapshotDecision] = {
            _action_key(d): d for d in baseline.decisions
        }
        current_by_key: dict[str, SnapshotDecision] = {
            _action_key(d): d for d in current.decisions
        }

        baseline_keys = set(baseline_by_key)
        current_keys = set(current_by_key)

        added: list[SnapshotDecision] = [
            current_by_key[k] for k in sorted(current_keys - baseline_keys)
        ]
        removed: list[SnapshotDecision] = [
            baseline_by_key[k] for k in sorted(baseline_keys - current_keys)
        ]
        changed: list[tuple[SnapshotDecision, SnapshotDecision]] = []

        for key in sorted(baseline_keys & current_keys):
            baseline_decision = baseline_by_key[key]
            current_decision = current_by_key[key]
            if baseline_decision != current_decision:
                changed.append((baseline_decision, current_decision))

        matches = not added and not removed and not changed

        return SnapshotDiff(
            matches=matches,
            added=added,
            removed=removed,
            changed=changed,
        )

    def assert_matches(
        self,
        current: GovernanceSnapshot,
        baseline_name: str,
    ) -> None:
        """Assert that the current snapshot matches the saved baseline.

        If no baseline exists under ``baseline_name``, the current snapshot is
        saved as the new baseline and the assertion passes. This allows the
        first run to establish the baseline automatically.

        On subsequent runs the current snapshot is compared against the saved
        baseline. Any difference causes an ``AssertionError`` with a detailed
        summary of what changed.

        Args:
            current: The snapshot taken from the current engine state.
            baseline_name: The name of the baseline to compare against, as
                used when calling ``save()``.

        Raises:
            AssertionError: If the current snapshot differs from the baseline.
        """
        file_path = self._snapshot_dir / f"{baseline_name}.snapshot.json"

        if not file_path.exists():
            # First run — save as baseline, assertion passes
            self.save(current, baseline_name)
            return

        baseline = self.load(baseline_name)
        diff = self.compare(current, baseline)

        assert diff.matches, (
            f"Governance snapshot '{baseline_name}' has changed.\n\n"
            f"{diff.summary()}\n\n"
            f"If this change is intentional, delete the baseline file and re-run "
            f"to establish a new baseline:\n"
            f"  {file_path}"
        )


# ---------------------------------------------------------------------------
# pytest fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def governance_snapshots(tmp_path: Path) -> GovernanceSnapshotManager:
    """Pytest fixture providing a GovernanceSnapshotManager backed by tmp_path.

    The snapshot directory is isolated per test invocation via pytest's
    ``tmp_path`` fixture — snapshots written in one test do not persist to
    another.

    For persistent baselines that survive across test runs, construct a
    ``GovernanceSnapshotManager`` directly with a stable directory path:

    .. code-block:: python

        SNAPSHOT_DIR = Path(__file__).parent / ".governance-snapshots"

        @pytest.fixture
        def stable_snapshots():
            return GovernanceSnapshotManager(SNAPSHOT_DIR)

    Example::

        def test_upload_policy(governance_engine, governance_snapshots):
            snapshot = governance_snapshots.capture(
                engine=governance_engine,
                test_actions=[
                    {"action": "file:upload", "agent_id": "level-3-agent"},
                ],
            )
            governance_snapshots.assert_matches(snapshot, "file-upload-policy")
    """
    return GovernanceSnapshotManager(tmp_path / "governance-snapshots")
