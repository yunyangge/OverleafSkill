# Setup and authentication

## Prerequisites

- Python 3.10 or newer and Git. Use the workspace's selected environment; if using Conda, activate it or prefix commands with `conda run -n <environment>`.
- An Overleaf project with Git integration and write access for publishing. Institutional/project-owner entitlements can provide Git access; do not assume the user's personal plan must be paid.
- Optional: Tectonic on PATH for local compilation. Online compilation uses Overleaf's existing TeX environment, so local TeX is unnecessary.
- macOS online login: install the repository's `requirements.txt` in the interpreter used to run MCP. When only the skill folder is installed, run `python -m pip install 'keyring==25.7.0'`. Windows uses the standard library only.

Examples below use `python` for the selected interpreter. On macOS this may be `python3`; on Windows `py -3.10`, or use Conda. Do not assume `python` resolves to the intended environment. Run scripts using absolute paths when outside the skill directory.

## Initialize a project

```sh
python scripts/manage.py --profile paper init --project https://www.overleaf.com/project/PROJECT_ID --repo /absolute/path/to/paper
```

On Windows use a path such as `D:/papers/paper`; on macOS `/Users/you/papers/paper`.
The script validates the ID, clones the project or verifies an existing dedicated checkout, and writes configuration outside the skill/repository. Existing profiles are not overwritten. Choose another profile for another project.
Git prompts locally for authentication if needed. Username is `git`; the password is an Overleaf Git authentication token. Use the OS Git credential helper so noninteractive MCP fetch/push can reuse the login. Never embed the token in a clone URL.

Configuration locations:

| OS | Local project configuration | Website session |
|---|---|---|
| Windows | `%LOCALAPPDATA%/OverleafSkill/<profile>.json` | DPAPI-encrypted `<profile>.dpapi` in the same directory |
| macOS | `~/Library/Application Support/OverleafSkill/<profile>.json` | native Keychain service `OverleafSkill.www.overleaf.com` |

Fields: `repo` (absolute checkout path), `online_project_id`, `session_profile`, optional `compiler` (absolute Tectonic executable).
Multiple profiles use separate MCP process names and configurations. Use only one active server per checkout; the server serializes its own requests but does not lock out external editors/processes.

## Website authentication (online compile only)

```sh
python scripts/manage.py --profile paper login
python scripts/manage.py --profile paper auth-status
```

Log into Overleaf in your browser. Open developer tools → Network; reload the project-list page; select its request and copy the **Cookie request header value**. Paste into the terminal's hidden prompt. This is a manual session import, not automatic browser login. The script verifies CSRF access and saves the cookie with OS protection; no plaintext fallback exists. On macOS, approve the native Keychain prompt if shown. A locked/unavailable keychain is an error, not a reason to store plaintext.

`logout` removes the local saved cookie; it does not revoke the browser/server session. Re-run login after expiry or a challenge. A Git login alone does not enable online compilation.

## Register MCP

```sh
python scripts/manage.py --profile paper doctor
python scripts/manage.py --profile paper register-codex
```

Registration adds `overleaf-paper`, using the current Python executable and absolute paths, and sets a 300-second tool timeout. It refuses to overwrite an existing server name. Review/remove an obsolete registration explicitly before replacing it. The skill's files must remain at that location; reinstall/register after moving them or changing interpreters.

For another MCP client:

```sh
python scripts/manage.py --profile paper mcp-config
```

This prints a generic `mcpServers` JSON entry; adapt only the outer configuration shape to that client's documented format. Use stdio and a tool timeout of at least 300 seconds. Restart/reload MCP connections as required by the client. `doctor` checks local handshake, tool enumeration and tracked-file listing; it does not prove remote authentication.

## Optional GitHub

Use an existing user-specified repository, or create a repository with the visibility the user authorized. For example, when GitHub CLI is installed and authenticated:

```sh
gh repo create OWNER/REPOSITORY --private
python scripts/manage.py --profile paper github --url https://github.com/OWNER/REPOSITORY.git
```

Use `--public` only when public publication was requested. GitHub authentication is independent from Overleaf; use the local GitHub/Git credential flow. Configuring a remote does not upload files. Push with `sync_github` after reviewing the committed version.

## Network and proxies

Inherit the user's known HTTP_PROXY/HTTPS_PROXY/NO_PROXY settings, or add them to the client's MCP server environment. Do not guess a proxy port or overwrite OS/global settings. Proxy values in public examples must be placeholders, not the maintainer's actual setup. Keep localhost direct if used for other services.

## Troubleshooting

- `LOGIN_REQUIRED_OR_CHALLENGE`: renew website session locally; do not send Git tokens to website endpoints.
- Git operation failed: verify origin, credential helper, network, branch upstream, and permissions in a local terminal. The server deliberately does not echo Git stderr that could include credentials.
- Protocol stdout contamination: launch with unbuffered Python; diagnostic output must go to stderr. Conda callers should use `--no-capture-output`.
- New tools absent: check registered command and reload the client's connection.
- Busy/limited compile: inspect status; do not spin in an automatic recompile loop.
- Source snapshot changes: inspect collaborator edits; the failed attempt's PDF is not presented as verified output.
