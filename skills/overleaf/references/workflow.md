# Tool contract and recovery

| Tool | Inputs | Effect |
|---|---|---|
| list_files | none | List tracked files in configured checkout |
| read_file | file | Read UTF-8 content and SHA-256, max 2 MB |
| patch_file | file, expected_sha256, old, new | Replace a unique exact snippet locally, preserving other bytes |
| show_diff | none | Return tracked changes, HEAD and content-bound review_id |
| sync_project | none | Fetch origin and fast-forward clean checkout; refuse local changes |
| publish_changes | review_id, message | Check review and remote HEAD, commit tracked changes, normal push to origin |
| sync_github | expected_commit | Push clean, committed HEAD to preconfigured github remote, no force |
| compile_project | file | Local Tectonic compilation; return log and PDF path |
| online_auth_status | none | Validate saved website session |
| compile_overleaf | none | Cloud compile using current Overleaf root/compiler settings; download log/PDF |

All inputs above are strings. Paths are project-relative with forward slashes. The server exposes the tools over MCP protocol 2025-03-26, newline-delimited stdio JSON-RPC. One server handles one project; use separate profiles/registrations for more projects.

## Normal editing

Sync → read → patch → show_diff → local compile if desired → authorized publish → online compile → optional authorized GitHub sync.
The user may authorize a whole workflow up front; do not re-request approval for already authorized publication. When they request only a draft or review, stop before publication. Preserve the paper's scientific claims and numbers unless the user specifically requests those changes.

## Recovery

- Stale file hash: re-read and reconcile; do not substitute a new hash without checking updated text.
- Ambiguous text: include more context. Avoid whole-section replacement based on a partial read.
- Stale review: inspect the new diff. The review ID includes HEAD and tracked-file bytes.
- Remote changes: all remote divergence blocks publish, even nonoverlapping edits. Review and merge/rebase locally under task authorization; the tool intentionally does not choose a conflict resolution.
- Push failure after commit: the commit stays local. Inspect status and remote history; retry the normal push only after reconciling. Do not repeat a write just because upload failed.
- Multi-file edits: patches are separate local operations, not a transaction. Review combined diff before publishing. A failed later patch does not undo earlier patches.

## Compilation semantics

Local compilation uses Tectonic with `--untrusted`, stores artifacts under `.git/overleaf-mcp-build`, and removes the previous PDF before invocation. Its package environment can differ from Overleaf. Timeout/error does not yield a successful PDF.

Cloud compilation requires a clean checkout whose Git HEAD matches the fetched upstream. It fetches a source ZIP before and after compilation, uses the CSRF-protected compile endpoint with stop-on-first-error, and downloads only returned build-scoped output URLs on `www.overleaf.com`. Each attempt gets a unique artifact directory `.git/overleaf-online-builds/<run_id>`.

Cloud success requires status success, matching before/after source snapshots, a log without detected fatal errors, and a PDF header. Warnings may remain; inspect full_log for diagnostics beyond the returned tail. This is conservative log screening, not a complete TeX parser or a visual layout review.

`source_verified_against_git` is always false: equal Git heads do not prove the website compiler consumed identical source. Archive snapshots do not exclude a transient edit during compilation that is later reverted. Report this accurately when discussing reproducibility. Live collaboration is not locked.

The tools return local paths, not public download URLs. Link/copy the requested artifact to the user's delivery location; do not add build outputs to source control by default.
