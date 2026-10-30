import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_server
from review import create


class Tests(unittest.TestCase):
    setUp = test_server.Tests.setUp
    tearDown = test_server.Tests.tearDown

    def test_operation_and_cumulative_diff_are_distinct(self):
        original = self.project.read('main.tex')
        first = self.project.patch('main.tex',original['sha256'],'Hello','First')
        report = first['review']
        saved = Path(report['html']).read_bytes()
        second = self.project.patch('main.tex',first['sha256'],'First','Second')
        latest = Path(second['review']['diff_file']).read_text()
        self.assertIn('-First',latest)
        self.assertNotIn('-Hello',latest)
        full = self.project.diff()
        self.assertIn('-Hello',full['diff'])
        self.assertEqual(Path(report['html']).read_bytes(), saved)
        self.assertEqual(full['review']['review_id'],full['review_id'])
        self.assertEqual(report['files'][0]['added'],1)
        self.assertEqual(report['files'][0]['removed'],1)
        self.assertEqual(self.project.git('status','--porcelain').decode().strip(),'M main.tex')

    def test_batch_and_undo_have_reviews(self):
        result = self.project.batch(json.dumps([{'operation':'create','file':'new.tex','text':'New'}]))
        self.assertEqual(result['review']['files'][0]['status'],'created')
        cumulative = self.project.diff()
        self.assertIn('new.tex', [f['file'] for f in cumulative['review']['files']])
        undo = self.project.undo(result['checkpoint'])
        self.assertEqual(undo['review']['files'][0]['status'],'deleted')
        self.assertEqual(self.project.diff()['review']['files'],[])

    def test_html_escapes_source_names_and_handles_binary_large_files(self):
        with tempfile.TemporaryDirectory() as d:
            report = create(d, {}, {'<img onerror=bad>.tex':b'<script>alert(1)</script>', 'figure.png':b'\0\xff', 'big.tex':b'x'*200_001}, 'operation')
            html = Path(report['html']).read_text(encoding='utf-8')
            self.assertNotIn('<script>',html)
            self.assertNotIn('<img',html)
            self.assertIn('&lt;img',html)
            self.assertIn('Binary asset',html)
            self.assertIn('Large file',html)
            self.assertIsNone(next(f for f in report['files'] if f['file']=='figure.png')['added'])

    def test_preview_failure_does_not_lose_successful_edit(self):
        original = self.project.read('main.tex')
        with patch('review.create',side_effect=OSError('disk')):
            result=self.project.patch('main.tex',original['sha256'],'Hello','Saved')
        self.assertIn('error',result['review'])
        self.assertIn('Saved',self.project.read('main.tex')['text'])
