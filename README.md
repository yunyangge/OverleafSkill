# OverleafSkill

A reproducible **Agent Skill + local MCP server** for Overleaf on **Windows and macOS**.

Use your existing assistant to read and edit LaTeX, review changes, publish through Overleaf Git, synchronize a GitHub repository, and compile locally or on Overleaf. No separate LLM API key is required.

中文：这是可安装的 skill 和配套 MCP 实现，包含完整搭建流程、10 个工具、认证管理、测试及故障恢复说明。论文、账号、Token 和本机路径不随仓库分发。

## What is included

| Capability | Implementation |
|---|---|
| Read/edit paper | Tracked UTF-8 files, exact-match patch, SHA-256 stale-read check |
| Review/publish | Diff-bound review ID, remote-head check, normal Git push |
| GitHub sync | Separate `github` remote, committed HEAD only, no force push |
| Local compilation | Optional Tectonic; logs and PDF |
| Overleaf compilation | Website session + CSRF, source snapshots, current build's logs/PDF |
| Website credentials | Windows DPAPI / macOS native Keychain |
| Setup | Portable Python commands, named profiles, generic MCP JSON, Codex registration |

## Quick start

Install Python 3.10+ and Git, then clone this public repository:

```sh
git clone https://github.com/yunyangge/OverleafSkill.git
cd OverleafSkill
python -m pip install -r requirements.txt
python install_skill.py
```

Use `python3` on macOS or `py -3.10` on Windows if appropriate. With Conda, use your selected environment, e.g. `conda run -n py310 python ...`. Windows core functionality has no pip dependencies; the requirement is conditional on macOS.

The installer copies only `skills/overleaf` to `$CODEX_HOME/skills/overleaf` (default `~/.codex/skills/overleaf`) and refuses to overwrite an existing skill. For another compatible agent, use `--dest` with its skill directory. It does not connect accounts, create repositories, or modify MCP settings by itself.

Ask your assistant:

> Use $overleaf to connect my Overleaf project and enable online compilation.

Or follow [the reproducible setup guide](skills/overleaf/references/setup.md) directly. It covers project URLs, Git authentication, website session import, optional GitHub, and client registration. Run its scripts from the **installed skill directory** so registration paths remain valid.

## Design

```text
Assistant / MCP client
         |
    local stdio server
         |-- Git ------ Overleaf project
         |         \--- optional GitHub remote
         |-- HTTPS ---- Overleaf online compiler
         |-- Tectonic - optional local compiler
         \-- OS store - website session (DPAPI / Keychain)
```

The skill supplies the operational workflow; the MCP server supplies deterministic tools. Read [SKILL.md](skills/overleaf/SKILL.md), [tool contracts](skills/overleaf/references/workflow.md), and [architecture/reproduction notes](skills/overleaf/references/architecture.md).

## Requirements and limits

Overleaf Git integration must be available for the project. Cloud compilation also needs a logged-in website session, imported locally through hidden input. Git authentication alone is insufficient. The server uses internal website endpoints, so future website changes may require updates.

Online builds compare cloud source snapshots before/after, but do **not** prove byte-for-byte identity with a Git commit or exclude transient concurrent edits. Files are patched individually; no cross-process or multi-file transaction is provided. Use a dedicated working copy per active server.

This release edits existing tracked text files. Project/file creation, binary upload, review comments and automatic background synchronization are outside its scope.

## Test

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

Git tests use temporary local repositories; cloud tests use simulated responses without credentials. GitHub Actions runs the suite on Windows and macOS. See [VALIDATION.md](VALIDATION.md) for what has actually been tested, including the distinction between CI and live account checks.

## License

MIT. Independent community project, not affiliated with Overleaf, GitHub, or OpenAI. External software and services retain their own terms.
