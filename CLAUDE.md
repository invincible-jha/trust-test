# trust-test — CLAUDE.md

## Project Identity

Package: `trust-test`
Sub-packages: `pytest-aumos-governance` (Python), `@aumos/vitest-governance` (TypeScript)
Purpose: Testing framework with governance-specific assertions for AumOS

## Repository Layout

```
trust-test/
├── python/                        # Python pytest plugin
│   ├── pyproject.toml
│   └── src/pytest_governance/
│       ├── plugin.py              # pytest registration + core fixtures
│       ├── assertions.py          # Standalone assertion functions
│       ├── fixtures.py            # Factory fixtures
│       └── matchers.py            # Fluent GovernanceDecisionMatcher
├── typescript/                    # TypeScript Vitest plugin
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsup.config.ts
│   └── src/
│       ├── index.ts               # Public exports
│       ├── matchers.ts            # Custom Vitest matchers
│       └── helpers.ts             # Test helper utilities
└── docs/
    ├── pytest-guide.md
    └── vitest-guide.md
```

## Key Design Decisions

### Independence
The Python and TypeScript packages are fully independent. They share no runtime
dependency on each other. Both depend on the `aumos-governance` / `@aumos/governance`
core package for types and engine access.

### No Mocking of the Engine
Fixtures provide a real `GovernanceEngine` configured for test use. This tests
actual governance logic — not stubs. Override config only when testing edge cases.

### Assertion Boundaries
`assert_trust_required` always tests BOTH sides of the boundary (level - 1 and level).
This guards against both false positives and false negatives in a single call.

### Fluent Matchers
`expect_decision()` / `governanceMatchers()` are the preferred interface for complex
decision assertions. Standalone assertion functions are kept for simple one-line checks.

## Coding Standards

- Python: type hints on all function signatures, `# SPDX-License-Identifier: Apache-2.0` header
- TypeScript: strict mode, no `any`, `// SPDX-License-Identifier: Apache-2.0` header
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- No production data, no forbidden identifiers (see FIRE_LINE.md)

## Running Locally

### Python
```bash
cd python
pip install -e ".[dev]"
pytest --governance
```

### TypeScript
```bash
cd typescript
pnpm install
pnpm build
```

## Release Process

1. Update `CHANGELOG.md` under `[Unreleased]`
2. Bump version in `python/pyproject.toml` and `typescript/package.json`
3. Tag as `trust-test-vX.Y.Z`
4. Publish Python to PyPI: `python -m build && twine upload dist/*`
5. Publish TypeScript to npm: `pnpm publish --access public`
