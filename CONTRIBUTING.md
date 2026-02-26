# Contributing to trust-test

Thank you for your interest in contributing to trust-test.
This package is part of the AumOS open-source ecosystem maintained by MuVeraAI Corporation.

## Before You Start

- Read `FIRE_LINE.md` — the hard constraints that must never be violated
- Read `CLAUDE.md` — project layout and design decisions
- Open an issue before starting significant work so we can align on approach

## Development Setup

### Python

```bash
cd python
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### TypeScript

```bash
cd typescript
pnpm install
pnpm build
```

## Making Changes

1. Branch from `main` using the convention: `feature/`, `fix/`, or `docs/`
2. Make focused, minimal edits — one logical change per commit
3. Add type hints on all new Python function signatures
4. Use TypeScript strict mode — no `any` types
5. Run lint and type-check before pushing

### Python checks

```bash
cd python
ruff check src/
mypy src/
```

### TypeScript checks

```bash
cd typescript
pnpm tsc --noEmit
```

## Commit Messages

Follow Conventional Commits:

```
feat: add assert_rate_limited assertion helper
fix: handle None reason in GovernanceDecisionMatcher.with_reason
docs: clarify budget_envelope fixture parameters
```

Commit messages explain WHY, not just WHAT.

## Pull Requests

- Keep PRs focused on a single concern
- Update `CHANGELOG.md` under `[Unreleased]`
- Ensure no real/production data is introduced (see FIRE_LINE.md)
- PRs are squash-merged to keep history clean

## Code of Conduct

Be direct, be respectful, and focus on technical merit.
MuVeraAI operates a first-principles engineering culture — assumptions should be
challenged with evidence, not authority.

## License

By contributing you agree that your contributions will be licensed under the Apache 2.0 License.
See `LICENSE` for the full text.
