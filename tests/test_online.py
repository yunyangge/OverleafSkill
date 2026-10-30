import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/overleaf/scripts"))
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from online import Meta, Online, archive_snapshot, output_url
from credentials import protect

PROJECT = "0123456789abcdef01234567"


def archive(text):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as z:
        z.writestr("main.tex", text)
    return result.getvalue()


class Fake(Online):
    def __init__(self, status="success", changed=False, log=b"Output written on output.pdf", pdf=b"%PDF-1.5\n", missing_log=False):
        super().__init__(PROJECT, cookie="test=value")
        self.status, self.changed, self.log, self.pdf = status, changed, log, pdf
        self.snapshots = 0
        self.missing_log = missing_log

    def request(self, path, body=None, **kwargs):
        if path == "/project":
            return b'<meta content="test&amp;csrf" name="ol-csrfToken">'
        if path.endswith("/download/zip"):
            self.snapshots += 1
            return archive("changed" if self.changed and self.snapshots > 1 else "source")
        if "/compile?" in path:
            assert kwargs["csrf"] == "test&csrf"
            assert body == {"stopOnFirstError": True}
            names = ["output.pdf"] if self.missing_log else ["output.pdf", "output.log"]
            return json.dumps({"status": self.status, "outputFiles": [
                {"path": name, "url": f"/project/{PROJECT}/build/build123/output/{name}"} for name in names]}).encode()
        if "output.pdf" in path:
            return self.pdf
        if "output.log" in path:
            return self.log
        raise AssertionError(path)


class Tests(unittest.TestCase):
    def test_success_and_unique_build_paths(self):
        with tempfile.TemporaryDirectory() as d:
            first = Fake().compile(d)
            second = Fake().compile(d)
            self.assertTrue(first["success"])
            self.assertNotEqual(first["pdf"], second["pdf"])
            self.assertTrue(Path(first["pdf"]).exists())
            self.assertFalse(first["source_verified_against_git"])

    def test_failure_does_not_expose_pdf(self):
        cases = [Fake(status="error"), Fake(changed=True), Fake(log=b"! Undefined control sequence."), Fake(missing_log=True)]
        with tempfile.TemporaryDirectory() as d:
            for case in cases:
                result = case.compile(d)
                self.assertFalse(result["success"])
                self.assertIsNone(result["pdf"])

    def test_html_is_not_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "not a PDF"):
                Fake(pdf=b"<html>login</html>").compile(d)

    def test_output_url_boundary(self):
        good = f"/project/{PROJECT}/build/a/output/output.pdf"
        self.assertEqual(output_url(PROJECT, good), "https://www.overleaf.com" + good)
        for bad in ["https://evil.test" + good, "//evil.test" + good,
                    good.replace(PROJECT, "0" * 24), good.replace("output.pdf", "../secret"),
                    good.replace("output.pdf", "%2e%2e/secret"), good.replace("output.pdf", "%252e%252e/secret"),
                    "https://www.overleaf.com@evil.test" + good]:
            with self.assertRaises(ValueError):
                output_url(PROJECT, bad)

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI")
    def test_dpapi_roundtrip(self):
        encrypted = protect(b"test-session-not-real")
        self.assertNotIn(b"test-session-not-real", encrypted)
        self.assertEqual(protect(encrypted, decrypt=True), b"test-session-not-real")

    def test_csrf_missing_is_auth_failure(self):
        client = Fake()
        client.request = lambda *args, **kwargs: b"<html>Sign in</html>"
        with self.assertRaisesRegex(RuntimeError, "LOGIN_REQUIRED"):
            client.csrf()


if __name__ == "__main__":
    unittest.main()
