"""Portable, explicit setup and maintenance commands. Run --help."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from credentials import state_dir, save_cookie, delete_cookie, validate_profile
from online import Online

HERE = Path(__file__).resolve().parent


def config_path(profile):
    return state_dir() / (validate_profile(profile) + ".json")


def read_config(profile):
    return json.loads(config_path(profile).read_text(encoding="utf-8-sig"))


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("Git " + args[0] + " failed; inspect the repository/authentication locally")
    return result.stdout.strip()


def mcp_config(profile):
    return {"command": sys.executable, "args": ["-u", str(HERE / "server.py"), str(config_path(profile))]}


def init(args):
    project = args.project.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"[a-fA-F0-9]{24}", project):
        raise ValueError("Provide an Overleaf project URL or 24-character project ID")
    target = config_path(args.profile)
    if target.exists():
        raise ValueError("Profile exists; use another --profile or edit its local config")
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").is_dir():
        if repo.exists() and any(repo.iterdir()):
            raise ValueError("Clone destination must be absent or empty")
        repo.parent.mkdir(parents=True, exist_ok=True)
        # Git handles credentials in the user's terminal; no token is placed in the URL.
        subprocess.run(["git", "clone", f"https://git@git.overleaf.com/{project}", str(repo)], check=True)
    remote = git(repo, "remote", "get-url", "origin")
    if remote not in (f"https://git.overleaf.com/{project}", f"https://git@git.overleaf.com/{project}"):
        raise ValueError("origin must point to the requested Overleaf project without a token in its URL")
    compiler = shutil.which(args.compiler) if args.compiler else shutil.which("tectonic")
    if args.compiler and not compiler:
        raise ValueError("Compiler executable not found")
    config = {"repo": str(repo), "online_project_id": project, "session_profile": args.profile}
    if compiler:
        config["compiler"] = compiler
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("Created local configuration:", target)
    print(json.dumps({"mcpServers": {"overleaf-" + args.profile: mcp_config(args.profile)}}, indent=2))


def doctor(profile):
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "doctor", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_files", "arguments": {}}}]
    result = subprocess.run([sys.executable, "-u", str(HERE / "server.py"), str(config_path(profile))],
                            input="\n".join(map(json.dumps, messages)) + "\n", text=True,
                            encoding="utf-8", capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Server startup failed: " + result.stderr)
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    if len(replies) != 3 or any("error" in r or r["result"].get("isError") for r in replies):
        raise RuntimeError("MCP protocol check failed")
    print("MCP handshake OK; tools:", len(replies[1]["result"]["tools"]))
    print("Tracked files:", len(json.loads(replies[2]["result"]["content"][0]["text"])))
    print("This checks local protocol/files only; it does not authenticate to remote services.")


def register(profile):
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("Codex CLI not found; use the mcp-config command for generic client configuration")
    name = "overleaf-" + profile
    # Avoid silently overwriting an existing server.
    existing = subprocess.run([executable, "mcp", "get", name], capture_output=True)
    if existing.returncode == 0:
        raise ValueError("MCP name exists; inspect/remove that registration before replacing it")
    subprocess.run([executable, "mcp", "add", name, "--", sys.executable, "-u", str(HERE / "server.py"), str(config_path(profile))], check=True)
    path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    contents = path.read_text(encoding="utf-8")
    header = "[mcp_servers." + name + "]\n"
    if contents.count(header) != 1:
        print("Set tool_timeout_sec = 300 in the registered server's configuration manually")
        return
    path.with_suffix(".toml.overleaf-backup").write_text(contents, encoding="utf-8")
    path.write_text(contents.replace(header, header + "tool_timeout_sec = 300\n", 1), encoding="utf-8")
    print("Registered. Reload the client's MCP connections or open a new session.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="default")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("init", help="Clone/use a dedicated Overleaf checkout; write local config")
    setup.add_argument("--project", required=True)
    setup.add_argument("--repo", required=True)
    setup.add_argument("--compiler", help="Optional Tectonic executable")
    for name in ("login", "browser-login", "logout", "doctor", "mcp-config", "register-codex", "auth-status", "compile-online"):
        sub.add_parser(name)
    exporting = sub.add_parser('export-profile')
    exporting.add_argument('--output', required=True)
    importing = sub.add_parser('import-profile')
    importing.add_argument('--manifest', required=True)
    importing.add_argument('--repo', required=True)
    importing.add_argument('--compiler')
    github = sub.add_parser("github", help="Add an existing GitHub repository as a second remote; does not push")
    github.add_argument("--url", required=True)
    args = parser.parse_args()
    validate_profile(args.profile)
    if args.command == "init":
        return init(args)
    if args.command == 'import-profile':
        from migration import read
        args.project = read(args.manifest)
        return init(args)
    if args.command == "logout":
        delete_cookie(args.profile)
        print("Website session removed from this computer (server-side session not revoked).")
        return
    if args.command == "mcp-config":
        print(json.dumps({"mcpServers": {"overleaf-" + args.profile: mcp_config(args.profile)}}, indent=2))
        return
    config = read_config(args.profile)
    if args.command == 'export-profile':
        from migration import export
        print(export(config, args.output))
    elif args.command == 'browser-login':
        from browser_login import login
        login(config['online_project_id'], args.profile)
    elif args.command == "login":
        print("Log into www.overleaf.com in your browser. Open DevTools > Network, reload /project,")
        print("select its request and copy Request Headers > Cookie (value only). Do not paste it into chat.")
        cookie = getpass.getpass("Cookie (hidden): ").strip()
        Online(config["online_project_id"], cookie=cookie).csrf()
        save_cookie(cookie, args.profile)
        print("Website session verified and saved in OS-protected storage.")
    elif args.command == "doctor":
        doctor(args.profile)
    elif args.command == "register-codex":
        register(args.profile)
    elif args.command == "github":
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.url):
            raise ValueError("Use a GitHub HTTPS repository URL without credentials")
        remotes = git(config["repo"], "remote").splitlines()
        if "github" in remotes:
            if git(config["repo"], "remote", "get-url", "github") != args.url:
                raise ValueError("github remote already points elsewhere; no changes made")
        else:
            git(config["repo"], "remote", "add", "github", args.url)
        print("GitHub remote configured. No files uploaded.")
    else:
        from server import Project, project_lock
        project = Project(config)
        with project_lock(project.root):
            result = project.online_status() if args.command == "auth-status" else project.online_compile()
        result.pop("log", None)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
