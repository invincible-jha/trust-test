# FIRE LINE — trust-test

This document records the inviolable constraints for this package.
Violation of any line below requires explicit sign-off from MuVeraAI engineering leadership.

---

## Hard Constraints

### NO production test data
Test fixtures must use synthetic, generated, or clearly labelled fake data only.
Real agent IDs, real budget figures, real decision records, or real audit logs from
any production or staging AumOS environment must never appear in this repository.

### NO forbidden identifiers
The following must never be committed:
- Real user or tenant identifiers
- Real organisation names beyond "MuVeraAI Corporation" (the licensor)
- API keys, secrets, tokens, or credentials of any kind
- PII of any form

### Both plugins work independently
The Python (`pytest-aumos-governance`) and TypeScript (`@aumos/vitest-governance`)
packages must have zero cross-language runtime dependency.
Each must be installable and functional without the other being present.

---

## Rationale

trust-test is a testing infrastructure package. Its role is to make governance
correctness verifiable — not to replicate governance logic or store sensitive data.
Keeping the two plugins independent ensures that polyglot teams can adopt only what
they need without pulling in unrelated runtimes.

---

_Last reviewed: 2026-02-26_
