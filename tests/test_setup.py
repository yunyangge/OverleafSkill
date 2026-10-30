import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/overleaf/scripts"))
import manage


class Tests(unittest.TestCase):
    def test_existing_checkout_setup_and_doctor(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            repo = folder / "paper"
            repo.mkdir()
            for args in [("init",), ("config", "user.name", "Test"), ("config", "user.email", "test@example.invalid"),
                         ("remote", "add", "origin", "https://git@git.overleaf.com/0123456789abcdef01234567")]:
                subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
            (repo / "main.tex").write_text("example", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "main.tex"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "test"], check=True, capture_output=True)
            config = folder / "state" / "paper.json"
            args = argparse.Namespace(project="https://www.overleaf.com/project/0123456789abcdef01234567",
                                      repo=str(repo), profile="paper", compiler=None)
            with patch.object(manage, "config_path", return_value=config), contextlib.redirect_stdout(io.StringIO()) as captured:
                manage.init(args)
                manage.doctor("paper")
                with self.assertRaisesRegex(ValueError, "exists"):
                    manage.init(args)
            self.assertIn("handshake OK", captured.getvalue())
            self.assertEqual(json.loads(config.read_text())["repo"], str(repo.resolve()))

    def test_installer_refuses_overwrite(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            args = [sys.executable, str(root / "install_skill.py"), "--dest", directory]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / "overleaf/SKILL.md").is_file())
            self.assertFalse(list(Path(directory).rglob("__pycache__")))
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
