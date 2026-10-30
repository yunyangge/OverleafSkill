import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/overleaf/scripts"))
import tempfile
import unittest
from unittest.mock import patch, Mock
import credentials


class Tests(unittest.TestCase):
    def test_mac_native_backend_routing(self):
        backend = Mock()
        backend.get_password.return_value = "session=test"
        with patch.object(credentials.sys, "platform", "darwin"), patch.object(credentials, "keychain", return_value=backend):
            credentials.save_cookie("session=test", "paper")
            self.assertEqual(credentials.load_cookie("paper"), "session=test")
            credentials.delete_cookie("paper")
        backend.set_password.assert_called_once_with(credentials.SERVICE, "paper", "session=test")
        backend.delete_password.assert_called_once_with(credentials.SERVICE, "paper")

    def test_native_failure_does_not_fallback_to_plaintext(self):
        with patch.object(credentials.sys, "platform", "darwin"), patch.object(credentials, "keychain", side_effect=RuntimeError("locked")):
            with self.assertRaisesRegex(RuntimeError, "locked"):
                credentials.save_cookie("session=test")

    def test_profile_traversal_rejected(self):
        for profile in ("../other", "a/b", "", "a\\b", "a:b"):
            with self.assertRaises(ValueError):
                credentials.load_cookie(profile)

    @unittest.skipUnless(sys.platform == "win32", "Windows session storage")
    def test_windows_profile_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(credentials, "state_dir", return_value=Path(directory)):
            credentials.save_cookie("session=test", "paper")
            self.assertEqual(credentials.load_cookie("paper"), "session=test")
            self.assertNotIn(b"session=test", (Path(directory) / "paper.dpapi").read_bytes())
            credentials.delete_cookie("paper")
            with self.assertRaisesRegex(RuntimeError, "LOGIN_REQUIRED"):
                credentials.load_cookie("paper")
