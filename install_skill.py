"""Copy the distributable skill, excluding runtime state. No account/config mutations."""
import argparse
import os
from pathlib import Path
import shutil
import uuid

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills")
    parser.add_argument('--upgrade', action='store_true')
    parser.add_argument('--restore', type=Path, help='Restore a saved skill backup; current skill is backed up first')
    args = parser.parse_args()
    source = args.restore.expanduser().resolve() if args.restore else Path(__file__).resolve().parent / "skills/overleaf"
    if not (source / 'SKILL.md').is_file():
        raise SystemExit('Source is not a skill directory')
    target = args.dest.expanduser().resolve() / "overleaf"
    if target.exists() and not (args.upgrade or args.restore):
        raise SystemExit("Skill already exists; inspect and back it up before replacing: " + str(target))
    if source == target or target in source.parents:
        raise SystemExit('Source must be separate from the installed skill')
    staging = target.with_name('overleaf-stage-' + uuid.uuid4().hex)
    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.dpapi", "config.json"))
    backup = None
    if target.exists():
        # Keep backups outside the discovery directory to avoid duplicate skill names.
        backup_root = target.parent.parent / 'overleaf-skill-backups'
        backup_root.mkdir(exist_ok=True)
        backup = backup_root / ('overleaf-backup-' + uuid.uuid4().hex)
        target.rename(backup)
        print('Previous skill backup:', backup)
    try:
        staging.rename(target)
    except Exception:
        if backup:
            backup.rename(target)
        raise
    print("Installed skill:", target)
    print("Next: follow references/setup.md; installing the skill does not register the MCP server.")
