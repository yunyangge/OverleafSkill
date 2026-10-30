import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_server
from test_server import git
from server import digest
from features import project_lock
from test_online import Fake, archive
from online import archive_snapshot, diagnostics


class Tests(unittest.TestCase):
    setUp = test_server.Tests.setUp
    tearDown = test_server.Tests.tearDown
    edit = test_server.Tests.edit
    def test_batch_undo_create_and_patch(self):
        original = self.project.read('main.tex')
        result = self.project.batch(json.dumps([
            {'operation':'patch','file':'main.tex','expected_sha256':original['sha256'],'old':'Hello','new':'New'},
            {'operation':'create','file':'figures/new.txt','text':'figure'}]))
        self.assertIn('figures/new.txt', self.project.files())
        self.project.diff()
        self.project.git('status','--porcelain')
        self.project.undo(result['checkpoint'])
        self.assertFalse((self.repo/'figures/new.txt').exists())
        self.assertEqual(self.project.read('main.tex'), original)

    def test_batch_prevalidation(self):
        original = self.project.read('main.tex')
        with self.assertRaises(ValueError):
            self.project.batch(json.dumps([
                {'operation':'patch','file':'main.tex','expected_sha256':original['sha256'],'old':'Hello','new':'New'},
                {'operation':'create','file':'../escape','text':'bad'}]))
        self.assertEqual(self.project.read('main.tex'),original)

    def test_undo_refuses_intervening_edit(self):
        result=self.project.batch(json.dumps([{'operation':'create','file':'new.tex','text':'one'}]))
        (self.repo/'new.tex').write_text('two')
        with self.assertRaises(ValueError): self.project.undo(result['checkpoint'])

    def test_retry_after_failed_push(self):
        self.edit()
        real=self.project.git
        def failure(*args):
            if args[0]=='push': raise RuntimeError('network')
            return real(*args)
        with patch.object(self.project,'git',side_effect=failure):
            with self.assertRaises(RuntimeError): self.project.publish(self.project.diff()['review_id'],'change')
        commit=self.project.head()
        self.assertTrue(self.project.retry_push(commit)['published'])
        self.assertEqual(git(self.remote,'rev-parse','HEAD').decode().strip(),commit)

    def test_lock_refuses_second_process_operation(self):
        with project_lock(self.repo):
            with self.assertRaisesRegex(RuntimeError,'PROJECT_BUSY'):
                with project_lock(self.repo): pass
        self.assertFalse((self.repo/'.git/overleaf-skill.lock').exists())

    def test_cloud_identity(self):
        with tempfile.TemporaryDirectory() as d:
            client=Fake()
            with self.assertRaisesRegex(RuntimeError,'CLOUD_SOURCE_MISMATCH'):
                client.compile(d,expected={'main.tex':'wrong'})
            self.assertEqual(client.snapshots,1)
            self.assertTrue(Fake().compile(d, expected=archive_snapshot(archive('source')))['source_verified_against_git'])

    def test_search_references(self):
        (self.repo/'main.tex').write_text('\\cite{missing}\\input{absent}')
        self.assertEqual(self.project.references()['missing_citations'],['missing'])
        self.assertEqual(len(self.project.search('missing')['hits']),1)
        self.assertTrue(diagnostics('main.tex:12: LaTeX Error: bad')[0]['line']==12)

    def test_async_compile(self):
        with patch.object(self.project,'online_compile',return_value={'success':True}):
            job=self.project.start_compile()['job_id']
            for _ in range(100):
                if self.project.job_status(job)['state']!='running': break
                time.sleep(.01)
            self.assertEqual(self.project.job_status(job)['state'],'completed')

    def test_binary_create_replace_delete(self):
        import base64
        value = b'\x89PNG\r\n\x00\xff'
        created = self.project.batch(json.dumps([{'operation':'create','file':'fig.png','base64':base64.b64encode(value).decode()}]))
        self.assertEqual(self.project.info('fig.png')['sha256'], digest(value))
        self.project.undo(created['checkpoint'])
        self.assertFalse((self.repo/'fig.png').exists())
        original = self.project.read('main.tex')
        deleted = self.project.batch(json.dumps([{'operation':'delete','file':'main.tex','expected_sha256':original['sha256']}]))
        self.project.undo(deleted['checkpoint'])
        self.assertEqual(self.project.read('main.tex'), original)

    def test_batch_aliases_refused(self):
        with self.assertRaises(ValueError):
            self.project.batch(json.dumps([{'operation':'create','file':'new.tex','text':'1'}, {'operation':'create','file':'./new.tex','text':'2'}]))
        self.assertFalse((self.repo/'new.tex').exists())

    def test_publish_created_and_deleted_files(self):
        original = self.project.read('main.tex')
        self.project.batch(json.dumps([{'operation':'create','file':'asset.bin','base64':'AP8='}, {'operation':'delete','file':'main.tex','expected_sha256':original['sha256']}]))
        self.project.publish(self.project.diff()['review_id'],'Review file changes')
        self.assertEqual(git(self.remote,'show','HEAD:asset.bin'),b'\x00\xff')
        self.assertNotIn('main.tex',git(self.remote,'ls-tree','--name-only','HEAD').decode())

    def test_failed_batch_restores_files_and_index(self):
        original = self.project.read('main.tex')
        real = self.project.git
        def fail(*args):
            if args[0] == 'add': raise RuntimeError('simulated failure')
            return real(*args)
        with patch.object(self.project,'git',side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.project.batch(json.dumps([{'operation':'patch','file':'main.tex','expected_sha256':original['sha256'],'old':'Hello','new':'New'}, {'operation':'create','file':'new.tex','text':'one'}]))
        self.assertEqual(self.project.read('main.tex'), original)
        self.assertFalse((self.repo/'new.tex').exists())
        self.assertFalse(self.project.git('status','--porcelain').strip())
