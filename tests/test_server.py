import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/overleaf/scripts"))
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from server import Project, digest


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.remote.mkdir()
        git(self.remote, "init", "--bare")
        self.repo = self.root / "paper"
        git(self.root, "clone", str(self.remote), str(self.repo))
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "main.tex").write_bytes(b"\\section{Intro}\r\nHello\r\n\\subsection{Keep}\r\nPreserved\r\n")
        git(self.repo, "add", "main.tex")
        git(self.repo, "commit", "-m", "Initial")
        git(self.repo, "push", "-u", "origin", "HEAD")
        self.project = Project({"repo": str(self.repo)})

    def tearDown(self):
        # Windows Git files can be read-only; retain fixtures in OS temp if cleanup is denied.
        self.temp.cleanup()

    def edit(self):
        s = self.project.read("main.tex")
        return self.project.patch("main.tex", s["sha256"], "Hello", "Changed")

    def test_patch_preserves_children_and_crlf_and_stays_local(self):
        before = self.project.head()
        self.edit()
        self.assertIn(b"\\subsection{Keep}\r\nPreserved", (self.repo / "main.tex").read_bytes())
        self.assertEqual(before, self.project.head())

    def test_stale_and_ambiguous_patch(self):
        s = self.project.read("main.tex")
        self.edit()
        with self.assertRaisesRegex(ValueError, "STALE_VERSION"):
            self.project.patch("main.tex", s["sha256"], "Hello", "Oops")
        s = self.project.read("main.tex")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            self.project.patch("main.tex", s["sha256"], "\\", "oops")

    def test_path_boundary(self):
        for name in ["../secret", ".git/config", "C:/secret", "/secret", "..\\secret"]:
            with self.assertRaises(ValueError):
                self.project.read(name)

    def test_publish_and_stale_review(self):
        review = self.project.diff()["review_id"]
        self.edit()
        with self.assertRaisesRegex(ValueError, "STALE_REVIEW"):
            self.project.publish(review, "edit")
        result = self.project.publish(self.project.diff()["review_id"], "Reviewed edit")
        self.assertTrue(result["published"])
        self.assertEqual(git(self.remote, "rev-parse", "HEAD").decode().strip(), result["commit"])

    def test_remote_change_blocks_publish(self):
        self.edit()
        other = self.root / "collaborator"
        git(self.root, "clone", str(self.remote), str(other))
        git(other, "config", "user.name", "Other")
        git(other, "config", "user.email", "other@example.invalid")
        (other / "main.tex").write_text("Collaborator version", encoding="utf-8")
        git(other, "commit", "-am", "Other edit")
        git(other, "push")
        with self.assertRaisesRegex(ValueError, "REMOTE_CHANGED"):
            self.project.publish(self.project.diff()["review_id"], "Must refuse")
        self.assertIn("Changed", self.project.read("main.tex")["text"])

    def test_sync_refuses_local_edits(self):
        self.assertEqual(self.project.sync()["head"], self.project.head())
        self.edit()
        with self.assertRaisesRegex(ValueError, "Local changes"):
            self.project.sync()

    def test_mcp_stdio(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"repo": str(self.repo)}))
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {"file": "main.tex"}}},
        ]
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "skills/overleaf/scripts/server.py"), str(config)],
                              input="\n".join(map(json.dumps, messages)) + "\n", capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(replies), 3)
        self.assertEqual(len(replies[1]["result"]["tools"]), 10)
        self.assertIn("sha256", replies[2]["result"]["content"][0]["text"])

    def test_github_refuses_dirty_and_stale(self):
        with self.assertRaisesRegex(ValueError, "STALE_COMMIT"):
            self.project.github_sync("wrong")
        self.edit()
        with self.assertRaisesRegex(ValueError, "Commit and review"):
            self.project.github_sync(self.project.head())

    @unittest.skipUnless(os.environ.get("OVERLEAF_TEST_COMPILE") == "1", "Optional compiler integration test")
    def test_local_compile(self):
        compiler = Path(__file__).resolve().parents[1] / "tectonic" / "tectonic.exe"
        if not compiler.exists():
            self.skipTest("Tectonic not installed")
        (self.repo / "main.tex").write_text("\\documentclass{article}\n\\begin{document}MCP test.\\end{document}\n", encoding="utf-8")
        project = Project({"repo": str(self.repo), "compiler": str(compiler)})
        result = project.compile("main.tex")
        self.assertTrue(result["success"], result["log"])
        self.assertTrue(Path(result["pdf"]).read_bytes().startswith(b"%PDF"))
        (self.repo / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\invalidcommandxyz\\end{document}\n", encoding="utf-8")
        result = project.compile("main.tex")
        self.assertFalse(result["success"])
        self.assertIsNone(result["pdf"])


if __name__ == "__main__":
    unittest.main()
