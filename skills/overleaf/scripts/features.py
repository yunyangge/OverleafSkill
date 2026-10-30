"""Recoverable editing, project locks, jobs and source inspection."""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid
from review import safe_create, parse_summaries


def sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


@contextmanager
def project_lock(root):
    path = root / '.git' / 'overleaf-skill.lock'
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('PROJECT_BUSY: another operation holds the lock. After a crash, verify its recorded PID is no longer running before removing the lock.')
    try:
        os.write(descriptor, json.dumps({'pid': os.getpid()}).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


class Features:
    def info(self, file):
        data = self.path(file).read_bytes()
        return {'file': file, 'size': len(data), 'sha256': sha(data)}

    def batch(self, changes, summaries=""):
        items = json.loads(changes)
        if not isinstance(items, list) or not 1 <= len(items) <= 50:
            raise ValueError('changes must be a JSON array of 1-50 operations')
        before, after, paths = {}, {}, set()
        for item in items:
            name = item['file']
            path = self.path(name)
            # Case-fold also on macOS/Windows to reject ambiguous portable paths.
            identity = str(path.resolve()).casefold()
            if identity in paths:
                raise ValueError('One operation per file per batch')
            paths.add(identity)
            old = path.read_bytes() if path.exists() else None
            if len(old or b'') > 20_000_000:
                raise ValueError('File exceeds 20 MB')
            if sha(old) != item.get('expected_sha256'):
                raise ValueError('STALE_VERSION: ' + name)
            operation = item['operation']
            if operation == 'patch':
                if old is None or not item.get('old') or old.decode('utf-8').count(item['old']) != 1:
                    raise ValueError('Patch must match one existing snippet')
                new = old.decode('utf-8').replace(item['old'], item['new'], 1).encode()
            elif operation == 'delete':
                if old is None:
                    raise ValueError('File does not exist')
                new = None
            elif operation in ('create', 'replace'):
                if operation == 'create' and old is not None:
                    raise ValueError('Create refuses existing files')
                new = base64.b64decode(item['base64'], validate=True) if 'base64' in item else item['text'].encode()
            else:
                raise ValueError('Unknown operation')
            if len(new or b'') > 20_000_000:
                raise ValueError('File exceeds 20 MB')
            before[name], after[name] = old, new
        if sum(len(v or b'') for v in before.values()) + sum(len(v or b'') for v in after.values()) > 50_000_000:
            raise ValueError('Batch exceeds 50 MB')
        notes = parse_summaries(summaries, after)
        identifier = uuid.uuid4().hex
        folder = self.root / '.git' / 'overleaf-checkpoints'
        folder.mkdir(exist_ok=True)
        index = self.root / '.git/index'
        original_index = index.read_bytes() if index.exists() else None
        encode = lambda value: base64.b64encode(value).decode() if value is not None else None
        receipt = {'head': self.head(), 'before': {k: encode(v) for k, v in before.items()},
                   'after': {k: sha(v) for k, v in after.items()}, 'index': encode(original_index)}
        checkpoint = folder / (identifier + '.json')
        checkpoint.write_text(json.dumps(receipt), encoding='utf-8')
        try:
            for name, value in after.items():
                path = self.path(name)
                if sha(path.read_bytes() if path.exists() else None) != sha(before[name]):
                    raise ValueError('File changed outside MCP during batch')
                self._put(path, value)
                if value is not None and before[name] is None:
                    self.git('add', '-N', '--', name)
            receipt['after_index'] = sha(index.read_bytes() if index.exists() else None)
            checkpoint.write_text(json.dumps(receipt), encoding='utf-8')
        except Exception:
            # Restore only files still equal to this batch's writes; don't overwrite external edits.
            for name, value in before.items():
                p = self.path(name)
                if sha(p.read_bytes() if p.exists() else None) == sha(after[name]):
                    self._put(p, value)
            self._put(index, original_index)
            raise
        return {'checkpoint': identifier, 'files': list(after), 'sha256': receipt['after'], 'published': False,
                'review': safe_create(self.root, before, after, 'operation', summaries=notes)}

    @staticmethod
    def _put(path, value):
        if value is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.overleaf-' + uuid.uuid4().hex)
            temporary.write_bytes(value)
            os.replace(temporary, path)

    def undo(self, checkpoint):
        if not re.fullmatch('[a-f0-9]{32}', checkpoint):
            raise ValueError('Invalid checkpoint')
        receipt = json.loads((self.root / '.git/overleaf-checkpoints' / (checkpoint + '.json')).read_text())
        if self.head() != receipt['head']:
            raise ValueError('HEAD changed; do not undo published/committed edits')
        index = self.root / '.git/index'
        if sha(index.read_bytes() if index.exists() else None) != receipt.get('after_index'):
            raise ValueError('Index changed or batch interrupted; inspect checkpoint manually')
        for name, expected in receipt['after'].items():
            path = self.path(name)
            if sha(path.read_bytes() if path.exists() else None) != expected:
                raise ValueError('File changed since checkpoint: ' + name)
        before = {name: self.path(name).read_bytes() if self.path(name).exists() else None for name in receipt['before']}
        after = {name: base64.b64decode(data) if data is not None else None for name,data in receipt['before'].items()}
        for name, data in after.items():
            self._put(self.path(name), data)
        self._put(index, base64.b64decode(receipt['index']) if receipt['index'] is not None else None)
        return {'restored': list(receipt['before']), 'review': safe_create(self.root, before, after, 'operation')}

    def retry_push(self, expected_commit):
        if self.head() != expected_commit or self.git('status', '--porcelain').strip():
            raise ValueError('Commit changed or worktree dirty')
        remote = self.fetch()
        if remote == expected_commit:
            return {'published': True, 'commit': expected_commit, 'already_present': True}
        try:
            self.git('merge-base', '--is-ancestor', remote, 'HEAD')
        except RuntimeError:
            raise ValueError('REMOTE_DIVERGED: reconcile before retrying')
        self.git('push', 'origin', 'HEAD')
        return {'published': True, 'commit': expected_commit}

    def summary(self):
        result = {'head': self.head(), 'changes': self.git('status', '--porcelain').decode(), 'remotes': {}}
        for remote in self.git('remote').decode().splitlines():
            try:
                self.git('fetch', remote)
                branch = self.git('symbolic-ref', '--short', 'HEAD').decode().strip()
                counts = self.git('rev-list', '--left-right', '--count', 'HEAD...' + remote + '/' + branch).decode().split()
                result['remotes'][remote] = {'ahead': int(counts[0]), 'behind': int(counts[1])}
            except RuntimeError:
                result['remotes'][remote] = {'status': 'unavailable_or_branch_missing'}
        try:
            result['website'] = self.online_status()
        except Exception as error:
            result['website'] = {'authenticated': False, 'reason': str(error)}
        receipts = list((self.root / '.git/overleaf-online-builds').glob('*/receipt.json'))
        if receipts:
            latest = json.loads(max(receipts, key=lambda p: p.stat().st_mtime).read_text(encoding='utf-8'))
            latest.pop('log', None)
            result['latest_compile'] = latest
        return result

    def search(self, query):
        hits = []
        if not query:
            raise ValueError('Empty query')
        for name in self.files():
            if Path(name).suffix not in ('.tex', '.bib', '.sty', '.cls', '.md'):
                continue
            try:
                text = self.read(name)['text']
            except (UnicodeError, OSError, ValueError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if query in line:
                    hits.append({'file': name, 'line': number, 'text': line[:1000]})
                    if len(hits) == 200:
                        return {'hits': hits, 'truncated': True}
        return {'hits': hits, 'truncated': False}

    def references(self):
        keys, cites, missing_inputs = set(), set(), []
        for name in self.files():
            if Path(name).suffix not in ('.tex', '.bib'):
                continue
            text = self.read(name)['text']
            text = re.sub(r'(?m)(?<!\\)%.*$', '', text)
            if name.endswith('.bib'):
                keys.update(re.findall(r'@\w+\s*\{\s*([^,\s]+)\s*,', text))
            else:
                for group in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}', text):
                    cites.update(k.strip() for k in group.split(',') if k.strip() != '*')
                for source in re.findall(r'\\(?:input|include)\{([^}]+)\}', text):
                    if '\\' in source or '#' in source:
                        continue
                    relative = source if Path(source).suffix else source + '.tex'
                    if not self.path(relative).exists() and not self.path(str(Path(name).parent / relative).replace('\\', '/')).exists():
                        missing_inputs.append({'file': name, 'input': source})
        return {'missing_citations': sorted(cites - keys), 'missing_inputs': missing_inputs,
                'note': 'Static heuristic only: does not expand TeX macros or verify literature authenticity.'}

    def start_compile(self):
        jobs = getattr(self, '_jobs', None)
        if jobs is None:
            self._jobs = jobs = {}
        if any(j['state'] == 'running' for j in jobs.values()):
            raise ValueError('A compile is already running')
        identifier = uuid.uuid4().hex
        jobs[identifier] = {'state': 'running'}
        def work():
            try:
                with project_lock(self.root):
                    result = self.online_compile()
                jobs[identifier] = {'state': 'completed', 'result': result}
            except Exception as error:
                jobs[identifier] = {'state': 'failed', 'error': str(error)}
        threading.Thread(target=work, daemon=True).start()
        return {'job_id': identifier, 'state': 'running'}

    def job_status(self, job_id):
        return getattr(self, '_jobs', {}).get(job_id, {'state': 'unknown', 'note': 'Job handles last only for the running MCP process; persisted compile receipts remain on disk.'})
