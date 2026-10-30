<div align="center">

<img src="assets/overleafskill-logo.png" alt="OverleafSkill logo: a paper sheet, leaf and version branch" width="140">

# OverleafSkill

**Let your AI assistant edit, sync, and compile your Overleaf project.**

[简体中文](README.md) · **English**

[![Tests](https://github.com/yunyangge/OverleafSkill/actions/workflows/test.yml/badge.svg)](https://github.com/yunyangge/OverleafSkill/actions/workflows/test.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Windows · macOS · Python 3.10+ · Skill + MCP

</div>

<p align="center">
  <img src="assets/overleafskill-hero.png" alt="OverleafSkill workflow: edit LaTeX, review diffs, sync Overleaf and GitHub, compile a PDF" width="100%">
  <br><sub>Edit → Review → Sync → Compile · Windows and macOS</sub>
</p>

Update a paper, inspect the diff, publish to Overleaf, compile online, and sync the reviewed version to GitHub. OverleafSkill packages this workflow as an installable skill and a reproducible local MCP server. Use your existing assistant; no additional model API key is required.

## Contents

- [Quick start](#quick-start)
- [Example requests](#example-requests)
- [Capabilities and tools](#capabilities-and-tools)
- [How it works](#how-it-works)
- [Platforms and validation](#platforms-and-validation)
- [Repository guide](#repository-guide)
- [FAQ](#faq)
- [Development and contributions](#development-and-contributions)

## Quick start

### 1. Install the skill

Install Python 3.10+ and Git, then use your selected Python environment:

```sh
git clone https://github.com/yunyangge/OverleafSkill.git
cd OverleafSkill
python -m pip install -r requirements.txt
python install_skill.py
```

Use `python3` on macOS or `py -3.10` on Windows as appropriate. Conda users can use `conda run -n py310 python ...`. Windows core functionality uses the standard library; macOS website session storage adds a Keychain dependency.

The default destination is `$CODEX_HOME/skills/overleaf`, or `~/.codex/skills/overleaf` when unset. The installer refuses to overwrite an existing skill. Use `--dest` for another compatible agent's skill directory.

### 2. Connect a project

Once the assistant has loaded the skill, ask:

```text
Use $overleaf to connect my project and enable online compilation.
Project: https://www.overleaf.com/project/YOUR_PROJECT_ID
```

**Installing the skill does not authenticate accounts or register MCP.** Complete Git authentication, project configuration, and client registration next. Online compilation also requires a separate website session, imported locally through hidden input. Never send credentials in chat.

The [setup guide](skills/overleaf/references/setup.md) covers Windows/macOS, multiple projects, proxies, Codex registration and generic MCP configuration. Other clients can use the generated configuration with their required outer format.

### 3. Verify the connection

From the **installed skill directory**, replace `paper` with your configured profile:

```sh
python scripts/manage.py --profile paper doctor
python scripts/manage.py --profile paper auth-status
```

`doctor` checks local MCP and file access; `auth-status` checks the website session. To reproduce a fixed code version, run `git checkout v1.0.0` before installation.

## Example requests

| Task | Ask your assistant |
|---|---|
| Edit and review | “Revise the second Introduction paragraph, preserve citations, and show the diff without pushing.” |
| Publish and compile | “Publish the reviewed changes to Overleaf, compile online, and return the PDF and diagnostics.” |
| Keep a GitHub copy | “Sync the current committed version to my specified private GitHub repository.” |
| Set up another computer | “Use $overleaf to recreate the connection on this Mac with a dedicated checkout.” |

The assistant interprets the requested edits; the skill guides the workflow and MCP executes file, sync and compile operations.

## Capabilities and tools

| Capability | MCP tools | Behavior |
|---|---|---|
| Read a paper | `list_files`, `read_file` | Tracked files, UTF-8 text and SHA-256 |
| Precise edits | `patch_file` | Stale-version check and unique exact-text replacement; local only |
| Review changes | `show_diff` | Diff and content-bound review ID |
| Overleaf sync | `sync_project`, `publish_changes` | Pull or publish; refuse publication when the remote has new commits |
| GitHub sync | `sync_github` | Push committed HEAD without force |
| Local compile | `compile_project` | Optional Tectonic; log and PDF |
| Online compile | `online_auth_status`, `compile_overleaf` | Website session check and download of this build's log/PDF |

See the [tool contract](skills/overleaf/references/workflow.md) for parameters, recovery and result semantics.

## How it works

```mermaid
flowchart LR
    A[AI assistant] --> S[Skill instructions]
    A --> M[Local MCP server]
    M --> G[Dedicated Git checkout]
    G <--> O[Overleaf project]
    G --> H[Optional GitHub repository]
    M --> C[Overleaf cloud compiler]
    M --> T[Optional local Tectonic]
    M --> K[DPAPI / Keychain session storage]
```

Typical flow: **sync → read → edit → review diff → authorized publish → compile → optional GitHub sync**.

Keep `origin` for Overleaf and `github` for GitHub. This is a local two-remote workflow, not Overleaf's built-in GitHub OAuth integration. Git uses the local credential helper; website sessions use Windows DPAPI or native macOS Keychain.

## Platforms and validation

| Check | Windows | macOS |
|---|---|---|
| Python 3.10 / 3.12 CI | Passed | Passed |
| Git, MCP, simulated cloud compilation | Passed | Passed |
| Native session storage | DPAPI round-trip passed | Keychain backend loads; read/write routing tested with mocks |
| Live Overleaf compilation | Original implementation verified | Not yet tested |

[CI results](https://github.com/yunyangge/OverleafSkill/actions/workflows/test.yml) · [Detailed validation record](VALIDATION.md)

Online compilation uses internal website endpoints that may change. Before/after cloud source snapshots are compared, but do not prove identity with a Git commit or exclude transient edits during compilation. Project/file creation, binary uploads, review comments and automatic background two-way sync are not supported.

## Repository guide

```text
OverleafSkill/
├── README.md / README.en.md       Chinese and English home pages
├── assets/                       Logo, hero and generation notes
├── install_skill.py              Skill installer
├── requirements.txt              Platform dependencies
├── skills/overleaf/
│   ├── SKILL.md                  Agent entry point
│   ├── agents/openai.yaml        Skill display metadata
│   ├── scripts/                  MCP, setup and authentication
│   └── references/               Setup, workflows and architecture
├── tests/                        Git, protocol, auth and compile tests
├── .github/workflows/            Windows/macOS CI
└── VALIDATION.md                 Evidence and limitations
```

Start with [setup.md](skills/overleaf/references/setup.md) for configuration, [workflow.md](skills/overleaf/references/workflow.md) for operations, or [architecture.md](skills/overleaf/references/architecture.md) to extend the implementation. The installable skill is self-contained; the entire repository is not required at runtime.

## FAQ

**Do I need a paid Overleaf account?** Git integration must be available for the project. Institutional or project-owner entitlements may provide access.

**Why import a website session if Git already works?** Git handles source synchronization. Cloud compilation uses a separate website authentication mechanism.

**Do I need local LaTeX?** Not for online compilation. Only the local compile tool requires Tectonic.

**Will edits be pushed automatically?** Edits stay local. Publication and GitHub sync are separate operations performed within your authorization.

**Does pulling this repository update the installed skill?** No. Installation copies files and refuses overwrites. Inspect and back up the installed version before replacing it, and re-register MCP if necessary. Project configurations and credentials live outside the skill directory.

## Development and contributions

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

Tests use temporary repositories and simulated cloud responses, without real accounts. Include your OS, Python version, reproduction steps and sanitized errors in reports; do not upload cookies, tokens or private papers. Keep capabilities and validation statements aligned across both README languages.

The homepage reading order and bilingual navigation were inspired by [CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills); the content describes OverleafSkill's own implementation.

MIT license. Independent community project, not affiliated with Overleaf, GitHub or OpenAI.
