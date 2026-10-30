# Tool contract and recovery

| Tool | Inputs | Effect |
|---|---|---|
| list_files | none | List tracked files in configured checkout |
| read_file | file | Read UTF-8 content and SHA-256, max 2 MB |
| patch_file | file, expected_sha256, old, new | Replace a unique exact snippet locally, preserving other bytes |
| show_diff | none | Return tracked changes, HEAD, content-bound review_id and offline visual review |
| sync_project | none | Fetch origin and fast-forward clean checkout; refuse local changes |
| publish_changes | review_id, message | Check review and remote HEAD, commit tracked changes, normal push to origin |
| sync_github | expected_commit | Push clean, committed HEAD to preconfigured github remote, no force |
| compile_project | file | Local Tectonic compilation; return log and PDF path |
| online_auth_status | none | Validate saved website session |
| compile_overleaf | none | Cloud compile using current Overleaf root/compiler settings; download log/PDF |
| file_info | file | SHA-256 and byte size, including binary assets |
| batch_edit | changes | JSON-encoded array of up to 50 edits; checkpoint before writing |
| undo_batch | checkpoint | Restore batch if HEAD, affected files and index still match |
| retry_publish | expected_commit | Retry normal push of clean committed HEAD; refuse divergence |
| project_status | none | Fetch remote ahead/behind counts, local changes, session and latest receipt |
| search_project | query | Literal text search, line numbers, up to 200 matches |
| check_references | none | Heuristic missing citation keys and input/include paths |
| start_online_compile | none | Start background compile in this process; return job_id |
| compile_status | job_id | Return running/completed/failed state and available result |

All inputs above are strings. Paths are project-relative with forward slashes. The server exposes the tools over MCP protocol 2025-03-26, newline-delimited stdio JSON-RPC. One server handles one project; use separate profiles/registrations for more projects.

## Normal editing

Sync → read → patch → show_diff → local compile if desired → authorized publish → online compile → optional authorized GitHub sync.
The user may authorize a whole workflow up front; do not re-request approval for already authorized publication. When they request only a draft or review, stop before publication. Preserve the paper's scientific claims and numbers unless the user specifically requests those changes.

## Visual review after every edit

`patch_file`, `batch_edit` and `undo_batch` return a `review` object for that operation's exact before/after bytes. `show_diff` returns a separate cumulative review of all uncommitted tracked changes relative to HEAD, including new files added through a batch. It may include pre-existing user edits: do not attribute all cumulative changes to the AI.

The object includes `html` (absolute path), `diff_file`, `scope`, creation time and per-file status, line counts, sizes and SHA-256 values. Open the HTML locally in any browser: it has file navigation, collapsible sections, side-by-side line numbers, red/green changes, underlined character changes, a changed-lines-only checkbox and a diff download. No server, JavaScript or external resources are needed. If the chat client opens HTML as text, use its open-in-browser action or open the file from the file manager.

After each logical editing round, provide a labeled link to `review.html` and a short summary in chat. Link the operation review as “this change”; label `show_diff` as “all uncommitted changes.” Prefer a batch for related files. Edits performed outside MCP need an explicit `show_diff` call. A report does not itself authorize publishing.

Snapshots are saved independently under `.git/overleaf-reviews/<id>/index.html`; they survive commits and subsequent edits. Their links are local, not public. Reports and text snapshots can contain private paper content; do not upload them without authorization. Binary files show size/hash metadata. Text comparisons above 200 KB total or 2,000 total lines offer full before/after text downloads instead of costly inline rendering. Line counts are null for those files; operation `.diff` downloads omit large/binary content and normalize text line endings, so they are review aids, not exact restoration patches. The cumulative `show_diff` download preserves Git's actual diff. Use checkpoints for undo.

Preview failure returns `review.error` without turning an already-saved edit into a reported failure. Report the edit as saved, use Git/text review, and do not repeat the edit just to regenerate its preview. Always obtain a fresh `show_diff`/review ID before publication; an old HTML page does not refresh or prove current state.

## Recovery

- Stale file hash: re-read and reconcile; do not substitute a new hash without checking updated text.
- Ambiguous text: include more context. Avoid whole-section replacement based on a partial read.
- Stale review: inspect the new diff. The review ID includes HEAD and tracked-file bytes.
- Remote changes: all remote divergence blocks publish, even nonoverlapping edits. Review and merge/rebase locally under task authorization; the tool intentionally does not choose a conflict resolution.
- Push failure after commit: the commit stays local. Inspect status and remote history, then call `retry_publish` with that exact commit. It only fast-forwards, treats an already-present commit as success, and refuses divergence. A fresh reviewed `publish_changes` on a clean checkout can also retry. Do not repeat edits because upload failed.
- Batch failure: all paths/hashes/content are checked before writing. Ordinary failures restore files still equal to this operation's writes and restore its index snapshot. A crash can leave partial changes; inspect `.git/overleaf-checkpoints` locally. Do not automatically replay or discard a partial batch.

## Batch and asset editing

`changes` is a JSON **string** containing an array, for example:

```json
[
  {"operation":"patch","file":"main.tex","expected_sha256":"HASH_FROM_READ_FILE","old":"unique old text","new":"new text"},
  {"operation":"create","file":"sections/new.tex","text":"New section"},
  {"operation":"create","file":"figures/icon.png","base64":"BASE64_FILE_BYTES"}
]
```

Use `file_info` for the hash of an existing binary asset. `replace` accepts `text` or `base64`; `delete` needs only file and expected_sha256. Existing files always require their current hash. A missing/null hash requires an absent file. Each path appears once per batch; limits are 20 MB per file and 50 MB total before/after data. Created files become visible in `show_diff` and the reviewed publish. For binary diffs, inspect the asset itself as needed; the review ID binds its bytes.

The result includes `checkpoint` and final hashes. `undo_batch` restores only an uncommitted batch whose affected files and Git index remain unchanged. It is not a revert of a published commit. Sequential batches can be undone in reverse order. Checkpoints contain source backups and belong only in the local `.git` directory.

MCP operations share a checkout lock at `.git/overleaf-skill.lock`. A busy operation returns PROJECT_BUSY. After an interrupted process, verify the recorded PID is gone before removing its lock. External editors/Git and Overleaf collaborators do not honor this lock; avoid concurrent outside writes. The CLI compile command honors the same lock. Individual file writes use replacement, but batches and undo are not atomic across a machine crash.

## Compilation semantics

Local compilation uses Tectonic with `--untrusted`, stores artifacts under `.git/overleaf-mcp-build`, and removes the previous PDF before invocation. Its package environment can differ from Overleaf. Timeout/error does not yield a successful PDF.

Cloud compilation requires a clean checkout whose Git HEAD matches the fetched upstream. Before invoking the compiler it compares every path/hash in a cloud source ZIP against committed Git blobs; `CLOUD_SOURCE_MISMATCH` stops the attempt. Known text types normalize CRLF to LF; binary assets compare exact bytes. It checks another source ZIP after compilation, uses the CSRF-protected compile endpoint with stop-on-first-error, and downloads only returned build-scoped output URLs on `www.overleaf.com`. Each attempt gets a unique artifact directory `.git/overleaf-online-builds/<run_id>`.

Cloud success requires status success, matching before/after source snapshots, a log without detected fatal errors, and a PDF header. Warnings may remain; inspect full_log for diagnostics beyond the returned tail. This is conservative log screening, not a complete TeX parser or a visual layout review.

`source_verified_against_git` is true only when both snapshots match the expected Git source. Receipts include `git_commit`, diagnostics and artifact paths. Archive checks do not exclude a transient edit during compilation that is later reverted. Report this accurately when discussing reproducibility. Live collaboration is not locked.

For long compiles, call `start_online_compile` then poll `compile_status` at reasonable intervals. `completed` means the job returned a result; inspect `result.success` to determine compilation success. Handles last only for the current MCP process and return `unknown` after restart; completed receipts remain on disk. Killing the process may interrupt a job. Concurrent jobs for the same checkout fail or are refused by its lock; no automatic retries/cancellation are provided.

`diagnostics` includes detected file/line errors and warnings, plus the full log path. Missing cite/input checks and log parsing are heuristics; they do not expand TeX macros or establish citation authenticity.

The tools return local paths, not public download URLs. Link/copy the requested artifact to the user's delivery location; do not add build outputs to source control by default.
