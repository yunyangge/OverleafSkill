import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/overleaf/scripts'))
import browser_login
import migration


class Tests(unittest.TestCase):
    def test_migration_excludes_local_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'project.json'
            config = {'online_project_id':'0'*24, 'repo':'private-path', 'cookie':'secret', 'compiler':'local-path'}
            migration.export(config, target)
            self.assertEqual(json.loads(target.read_text()), {'format':1,'online_project_id':'0'*24})
            self.assertEqual(migration.read(target),'0'*24)
            with self.assertRaises(ValueError): migration.export(config,target)

    def test_upgrade_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            destination = Path(d)/'skills'
            def install(*args):
                return subprocess.run([sys.executable, str(ROOT/'install_skill.py'), '--dest', str(destination), *args],capture_output=True,text=True)
            self.assertEqual(install().returncode,0)
            marker = destination/'overleaf/local-marker.txt'
            marker.write_text('keep')
            self.assertNotEqual(install().returncode,0)
            self.assertEqual(install('--upgrade').returncode,0)
            self.assertFalse(marker.exists())
            backup = next((Path(d)/'overleaf-skill-backups').glob('overleaf-backup-*'))
            self.assertEqual((backup/'local-marker.txt').read_text(),'keep')
            self.assertEqual(install('--restore',str(backup)).returncode,0)
            self.assertEqual(marker.read_text(),'keep')

    def test_browser_login_saves_only_after_validation(self):
        api = types.ModuleType('playwright.sync_api')
        api.sync_playwright = MagicMock()
        browser = api.sync_playwright.return_value.__enter__.return_value.chromium.launch.return_value
        browser.new_context.return_value.cookies.return_value = [{'name':'session','value':'test-only'}]
        with patch.dict(sys.modules, {'playwright':types.ModuleType('playwright'), 'playwright.sync_api':api}), patch('builtins.input',return_value=''), patch.object(browser_login,'Online') as online, patch.object(browser_login,'save_cookie') as save:
            browser_login.login('0'*24,'test')
            online.return_value.csrf.assert_called_once()
            save.assert_called_once_with('session=test-only','test')
            browser.close.assert_called_once()
            save.reset_mock()
            online.return_value.csrf.side_effect = RuntimeError('expired')
            with self.assertRaises(RuntimeError): browser_login.login('0'*24,'test')
            save.assert_not_called()
