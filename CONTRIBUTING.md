# Contributing to `ellmos-homebase-mcp`

Thank you for contributing to **ellmos-homebase-mcp**!

## Architecture & Core Invariants

Before making changes, please review:

- [MODE-CONTRACT.md](MODE-CONTRACT.md): Binding rules for `canonical` vs. `bundled` engine modes. Unreachable canonical targets MUST fail closed rather than silently falling back to bundled SQLite databases.
- [SECURITY.md](SECURITY.md): 100% local-first, zero-egress, non-elevation (`RunAsInvoker`), and vulnerability reporting channels.
- [README.md](README.md) / [README_de.md](README_de.md): Bilingual parity (`en` / `de`) and schema localization (`en`, `de`, `es`, `zh`, `ja`, `ru` in `src/homebase/i18n.py`).

## Development Workflow

1. Fork and clone the repository to a non-cloud-synced local workspace.
2. Create a dedicated feature or fix branch from `main` (do not push directly to `main`).
3. Install in editable mode with dev dependencies:

```bash
python -m pip install -e ".[dev]" ruff
```

4. Make focused, well-tested changes. Do **not** bump package versions in feature/hygiene PRs unless preparing an explicit release.

## Local Verification Gate

Run all verification checks before opening a pull request:

```bash
ruff check .
python -m pip check
python -m pytest -ra -v
python -m compileall -q src tests
git diff --check
npm run smoke
npm pack --dry-run --json
```

## Pull Request Checklist

- [ ] Tests pass (`pytest`) with new/updated contract or unit tests for your change
- [ ] `ruff check .` passes cleanly with zero warnings/errors
- [ ] Bilingual documentation (`README.md` / `README_de.md`) and `CHANGELOG.md` (`## [Unreleased]`) updated where applicable
- [ ] No local databases (`*.db`), `.env` files, secrets, or lock files committed

---

## Beitragsleitfaden (Deutsche Kurzfassung)

1. Änderungen immer auf einem eigenen Branch ab `main` entwickeln und per Pull Request einreichen.
2. Vor dem PR lokal prüfen: `ruff check .`, `python -m pip check`, `python -m pytest -ra -v`, `python -m compileall -q src tests`, `npm run smoke` und `npm pack --dry-run --json`.
3. `MODE-CONTRACT.md` (Fail-Closed bei unerreichbaren kanonischen Engines), Zero-Egress-Garantien und die 6-Sprachen-Parität in `i18n.py` strikt wahren.
