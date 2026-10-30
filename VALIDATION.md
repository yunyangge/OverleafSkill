# Validation record

## 2026-10-30

### v1.1 additions

- Windows Python 3.10: checkpoint undo, batch prevalidation/rollback, path alias rejection, binary asset hashes, file create/delete publication, failed-push retry, lock contention, Git/cloud mismatch preflight, asynchronous compile completion, search and diagnostic parsing are covered by isolated tests.
- Installer upgrade/restore preserves the prior installation; migration manifests exclude machine paths and credentials. Interactive browser login is tested with mocked Playwright/session storage, including authentication failure refusing to save a cookie.
- MCP stdio smoke test enumerates 19 tools. The skill frontmatter validator passes.
- A read-only check against the maintainer's existing authenticated Windows project verified that all 72 cloud archive files match committed Git blobs using the new comparison. No paper source or credential is distributed.
- The installed v1.1 implementation subsequently completed an authenticated cloud compile, downloaded the PDF/log and recorded `source_verified_against_git: true` with its Git commit. Existing formatting/font warnings were returned as diagnostics; this was not a visual paper review. The source checkout was not edited or published during validation.
- The Windows installation and existing MCP registration were upgraded with backups, preserving the project checkout and authentication. A local protocol check found all 19 tools. Playwright 1.64.1 and its Chromium browser were installed; interactive login remains mock-tested.
- New cross-platform CI results are linked from the repository badge. Browser interaction/SSO/challenges and native macOS Keychain login still require live interactive validation; no live account is used by CI.
- Snapshot identity is not a cloud compiler lock. Batches are not crash-atomic, locks are advisory to this implementation, and async handles are process-local. These limits are documented in the tool contract.

### Original release evidence

- The original Windows implementation completed a real authenticated Overleaf cloud compilation and downloaded its PDF and log. No paper source is included here.
- The portable release retains that compilation adapter and adds per-profile OS-backed sessions, a portable CLI, installer and reproducible tests.
- Windows Python 3.10: local Git operations, stale-read/review rejection, remote update rejection, MCP handshake and simulated compilation are tested. DPAPI encryption/decryption uses the real OS API.
- macOS: native Keychain is selected explicitly; routing is covered by mocks. An interactive macOS Keychain login and live Overleaf compile have not been performed by the maintainer on this release.
- GitHub Actions matrix: Windows/macOS × Python 3.10/3.12. The live checks badge/results are authoritative; having a workflow file alone does not mean it passed.
- Tectonic integration is optional (OVERLEAF_TEST_COMPILE=1) and is not part of default CI. The original Windows implementation passed good-document and error-document compilation tests.

No credentials or real projects are needed for CI. Do not add account cookies to CI to turn simulation into a live test.
