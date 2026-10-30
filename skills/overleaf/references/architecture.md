# Reproduction and extension

## Components

- `server.py`: project-scoped Git operations, hash-based edits, review-bound publish, local compiler and small MCP stdio dispatcher.
- `online.py`: website CSRF, bounded HTTPS requests with redirects disabled, source ZIP fingerprints, build-specific output validation, compilation receipts.
- `credentials.py`: Windows current-user DPAPI or explicitly selected macOS Keychain backend; no token in command arguments and no plaintext fallback.
- `manage.py`: portable setup, session import, generic client configuration, optional Codex registration, diagnosis, GitHub remote setup.
- `features.py`: checkout locks, recoverable batches/checkpoints, push retries, status/search/reference helpers and asynchronous compile handles.
- `review.py`: escaped, offline HTML before/after snapshots, line/character highlighting, diff and text downloads; immutable per-operation reports under `.git`.
- `browser_login.py`: optional isolated interactive Playwright login; credential storage is delegated to credentials.py.
- `migration.py`: versioned project-ID-only manifests; no credential or machine-path export.
- Root `install_skill.py`: staged install, upgrade backup and restore; does not alter project state.

Git credentials remain with Git's configured credential helper. Website cookies stay in OS storage. Both source checkouts and generated configuration belong outside this skill's distributable files. GitHub is a second remote, not Overleaf's built-in GitHub OAuth integration.

## Reproduce

1. Install Python 3.10+, Git, and the pinned macOS keyring requirement if applicable.
2. Run `python -m unittest discover -s tests -p "test_*.py" -v` from repository root.
3. Install the skill with the root install script or the host's skill installer.
4. Follow setup.md using a test project with Git integration.
5. Run doctor, auth-status, and compile-online. Review the receipt and actual PDF. For write testing, use a disposable project; don't edit production just to verify installation.

Tests use temporary local bare Git remotes and fake cloud responses. Windows DPAPI runs natively on Windows. The macOS backend routing is tested with a fake Keychain object; user Keychain and live login need an interactive Mac validation. CI runs Git/protocol/online simulations on Windows and macOS without account secrets. The optional Tectonic test is enabled with OVERLEAF_TEST_COMPILE=1 when Tectonic is installed.

## Current exclusions and extension points

No comments/review panel, Overleaf project creation/deletion, SSH Overleaf remote, HTTP MCP transport, or automatic two-way background sync. Project files and binary assets can be created/replaced/deleted through reviewed Git publication. Browser login remains user-interactive. Multi-project support is separate process/profile per checkout.

Batch checkpoints and completed compilation receipts persist under `.git`; asynchronous job handles are process-local. Checkout locks coordinate this implementation's MCP processes and CLI compilation, not external editors or cloud collaboration. Batch rollback handles ordinary exceptions; recovery from power loss/interrupted writes requires inspecting the local checkpoint. No distributed transaction or compiler-source lock is claimed.

For additional tools, change both descriptor and dispatch mapping, validate arguments, and test observable outcomes. Keep stdout reserved for JSON-RPC. Expensive operations need a bounded timeout. Avoid force push, destructive rollback, or treating an existing PDF as evidence of a successful new build.

## Upstream interfaces

- [Overleaf Git integration](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration)
- [MCP stdio lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
- Compile route/output fields were cross-checked against [overleaf-latex's client](https://github.com/MarcoDotIO/overleaf-latex/blob/main/src/overleaf-client.ts). This repository does not vendor that client.

The website endpoints are internal interfaces, not a stable public Overleaf API. This is an independent community integration, not an official Overleaf product.
