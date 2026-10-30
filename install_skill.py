"""Copy the distributable skill, excluding runtime state. No account/config mutations."""
import argparse
import os
from pathlib import Path
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / "skills/overleaf"
    target = args.dest.expanduser().resolve() / "overleaf"
    if target.exists():
        raise SystemExit("Skill already exists; inspect and back it up before replacing: " + str(target))
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.dpapi", "config.json"))
    print("Installed skill:", target)
    print("Next: follow references/setup.md; installing the skill does not register the MCP server.")
