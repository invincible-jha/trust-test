# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""pytest-aumos-governance: pytest plugin for AumOS governance testing.

This package provides pytest fixtures, assertion helpers, and fluent matchers
for writing governance-correctness tests against AumOS GovernanceEngine instances.

Public API
----------
- Fixtures:   governance_engine, trust_manager, budget_manager,
              governed_agent, budget_envelope   (via plugin auto-registration)
- Assertions: see pytest_governance.assertions
- Matchers:   see pytest_governance.matchers
"""

from pytest_governance.assertions import (
    assert_audit_contains,
    assert_budget_exceeded,
    assert_budget_sufficient,
    assert_consent_required,
    assert_governance_denied,
    assert_governance_permitted,
    assert_trust_required,
)
from pytest_governance.matchers import GovernanceDecisionMatcher, expect_decision

__all__ = [
    # assertions
    "assert_trust_required",
    "assert_budget_sufficient",
    "assert_budget_exceeded",
    "assert_consent_required",
    "assert_governance_denied",
    "assert_governance_permitted",
    "assert_audit_contains",
    # matchers
    "GovernanceDecisionMatcher",
    "expect_decision",
]

__version__ = "0.1.0"
