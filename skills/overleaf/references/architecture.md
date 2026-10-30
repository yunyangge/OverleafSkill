# Reproduction and extension

## Components

- `server.py`: project-scoped Git operations, hash-based edits, review-bound publish, local compiler and small MCP stdio dispatcher.
- `online.py`: website CSRF, bounded HTTPS requests with redirects disabled, source ZIP fingerprints, build-specific output validation, compilation receipts.
- `credentials.py`: Windows current-user DPAPI or explicitly selected macOS Keychain backend; no token in command arguments and no plaintext fallback.
- `manage.py`: portable setup, session import, generic client configuration, optional Codex registration, diagnosis, GitHub remote setup.

Git credentials remain with Git's configured credential helper. Website cookies stay in OS storage. Both source checkouts and generated configuration belong outside this skill's distributable files. GitHub is a second remote, not Overleaf's built-in GitHub OAuth integration.

## Reproduce

1. Install Python 3.10+, Git, and the pinned macOS keyring requirement if applicable.
2. Run `python -m unittest discover -s tests -p "test_*.py" -v` from repository root.
3. Install the skill with the root install script or the host's skill installer.
4. Follow setup.md using a test project with Git integration.
5. Run doctor, auth-status, and compile-online. Review the receipt and actual PDF. For write testing, use a disposable project; don't edit production just to verify installation.

Tests use temporary local bare Git remotes and fake cloud responses. Windows DPAPI runs natively on Windows. The macOS backend routing is tested with a fake Keychain object; user Keychain and live login need an interactive Mac validation. CI runs Git/protocol/online simulations on Windows and macOS without account secrets. The optional Tectonic test is enabled with OVERLEAF_TEST_COMPILE=1 when Tectonic is installed.

## Current exclusions and extension points

No comments/review panel, project CRUD, binary uploads, SSH Overleaf remote, automatic browser login, HTTP MCP transport, cross-process locking, or automatic two-way background sync. Multi-project support is separate process/profile per checkout.

For additional tools, change both descriptor and dispatch mapping, validate arguments, and test observable outcomes. Keep stdout reserved for JSON-RPC. Expensive operations need a bounded timeout. Avoid force push, destructive rollback, or treating an existing PDF as evidence of a successful new build.

## Upstream interfaces

- [Overleaf Git integration](https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration)
- [MCP stdio lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle)
- [Python keyring](https://keyring.readthedocs.io/en/stable/)
- Compile route/output fields were cross-checked against [overleaf-latex's client](https://github.com/MarcoDotIO/overleaf-latex/blob/main/src/overleaf-client.ts). This repository does not vendor that client.

The website endpoints are internal interfaces, not a stable public Overleaf API. This is an independent community integration, not an official Overleaf product.
