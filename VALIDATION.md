# Validation record

## 2026-10-30

- The original Windows implementation completed a real authenticated Overleaf cloud compilation and downloaded its PDF and log. No paper source is included here.
- The portable release retains that compilation adapter and adds per-profile OS-backed sessions, a portable CLI, installer and reproducible tests.
- Windows Python 3.10: local Git operations, stale-read/review rejection, remote update rejection, MCP handshake and simulated compilation are tested. DPAPI encryption/decryption uses the real OS API.
- macOS: native Keychain is selected explicitly; routing is covered by mocks. An interactive macOS Keychain login and live Overleaf compile have not been performed by the maintainer on this release.
- GitHub Actions matrix: Windows/macOS × Python 3.10/3.12. The live checks badge/results are authoritative; having a workflow file alone does not mean it passed.
- Tectonic integration is optional (OVERLEAF_TEST_COMPILE=1) and is not part of default CI. The original Windows implementation passed good-document and error-document compilation tests.

No credentials or real projects are needed for CI. Do not add account cookies to CI to turn simulation into a live test.
