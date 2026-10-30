"""Overleaf website compilation adapter. No Git token or browser profile scraping."""
import ctypes
from ctypes import wintypes
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlsplit, unquote, urlencode, parse_qsl, urlunsplit
import uuid
import zipfile

ORIGIN = "https://www.overleaf.com"


from credentials import load_cookie


class Meta(HTMLParser):
    token = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "ol-csrfToken":
            self.token = attrs.get("content")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def output_url(project, value):
    url = urljoin(ORIGIN, value)
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "www.overleaf.com" or parts.fragment
            or re.search(r"[\\\x00-\x20]", value)):
        raise ValueError("Untrusted compile output URL")
    for segment in parts.path.split("/"):
        decoded = unquote(segment)
        if decoded in (".", "..") or re.search(r"[/\\%\x00-\x1f]", decoded):
            raise ValueError("Unsafe output path")
    pattern = rf"^/(?:download/)?project/{re.escape(project)}/(?:user/[a-fA-F0-9]{{24}}/)?build/[A-Za-z0-9_-]+/output/.+$"
    if not re.match(pattern, parts.path):
        raise ValueError("Output does not belong to this project's build")
    return url


def source_hash(name, data):
    if Path(name).suffix.lower() in ('.tex', '.bib', '.sty', '.cls', '.bst', '.md', '.txt', '.json'):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def diagnostics(log):
    entries = []
    for line in log.splitlines():
        match = re.match(r'(.+?):(\d+):\s*(.+)', line)
        if match:
            entries.append({'file': match[1], 'line': int(match[2]), 'message': match[3], 'level': 'error' if 'error' in match[3].lower() else 'info'})
        elif line.startswith('!') or 'Warning:' in line or line.startswith(('Overfull ', 'Underfull ')):
            entries.append({'file': None, 'line': None, 'message': line, 'level': 'error' if line.startswith('!') else 'warning'})
    return entries[:500]


def archive_snapshot(data):
    snapshot = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100_000_000:
            raise ValueError("Source archive exceeds 100 MB")
        for item in archive.infolist():
            if not item.is_dir():
                if item.filename in snapshot:
                    raise ValueError("Duplicate archive path")
                snapshot[item.filename] = source_hash(item.filename, archive.read(item))
    return snapshot


class Online:
    def __init__(self, project, cookie=None, profile="default"):
        if not re.fullmatch(r"[a-fA-F0-9]{24}", project):
            raise ValueError("Invalid Overleaf project ID")
        self.project = project
        self.cookie = cookie if cookie is not None else load_cookie(profile)
        if not self.cookie or "\n" in self.cookie or "\r" in self.cookie:
            raise ValueError("Invalid session cookie")
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, body=None, csrf=None, limit=50_000_000):
        url = urljoin(ORIGIN, path)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.overleaf.com":
            raise ValueError("Refusing credentials outside Overleaf")
        headers = {"Cookie": self.cookie, "Origin": ORIGIN, "Referer": ORIGIN + "/project/" + self.project,
                   "User-Agent": "Mozilla/5.0 OverleafMCP/0.2", "Accept": "application/json" if body is not None else "*/*"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with self.opener.open(req, timeout=180 if body is not None else 30) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise RuntimeError("Overleaf response exceeds size limit")
                return data
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308, 401, 403):
                raise RuntimeError("LOGIN_REQUIRED_OR_CHALLENGE: renew the local website session") from None
            raise RuntimeError("Overleaf HTTP error " + str(exc.code)) from None
        except urllib.error.URLError:
            raise RuntimeError("Overleaf network request failed; check proxy and connection") from None

    def csrf(self):
        page = self.request("/project", limit=8_000_000).decode("utf-8")
        parser = Meta()
        parser.feed(page)
        if not parser.token:
            raise RuntimeError("LOGIN_REQUIRED_OR_CHALLENGE: could not obtain a website CSRF token")
        return parser.token

    def compile(self, destination, expected=None):
        csrf = self.csrf()
        before = archive_snapshot(self.request(f"/project/{self.project}/download/zip"))
        if expected is not None and before != expected:
            differing = sorted(k for k in set(before) | set(expected) if before.get(k) != expected.get(k))
            raise RuntimeError('CLOUD_SOURCE_MISMATCH: compile not started; differing paths: ' + ', '.join(differing[:30]))
        response = json.loads(self.request(f"/project/{self.project}/compile?file_line_errors=true",
                                          {"stopOnFirstError": True}, csrf=csrf))
        status = response.get("status")
        outputs = response.get("outputFiles", [])
        if not isinstance(status, str) or not isinstance(outputs, list):
            raise RuntimeError("Unexpected compile response; website adapter needs updating")
        run_id = uuid.uuid4().hex
        target = Path(destination) / run_id
        target.mkdir(parents=True)
        downloaded = {}
        for item in outputs:
            if not isinstance(item, dict) or item.get("path") not in ("output.log", "output.pdf"):
                continue
            name = item["path"]
            if name in downloaded:
                raise RuntimeError("Duplicate compile output descriptor")
            url = output_url(self.project, item["url"])
            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query))
            for source, key in (("clsiServerId", "clsiserverid"), ("compileGroup", "compileGroup")):
                if isinstance(response.get(source), str):
                    query[key] = response[source]
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
            data = self.request(url)
            if name.endswith(".pdf") and not data.startswith(b"%PDF-"):
                raise RuntimeError("Compile output is not a PDF")
            (target / name).write_bytes(data)
            downloaded[name] = data
        after = archive_snapshot(self.request(f"/project/{self.project}/download/zip"))
        stable = before == after
        log = downloaded.get("output.log", b"").decode("utf-8", errors="replace")
        has_error = bool(re.search(r"(?m)^!|^.+:\d+: (?:LaTeX |Package .+ )?Error|Fatal error occurred", log))
        success = status == "success" and stable and "output.log" in downloaded and "output.pdf" in downloaded and not has_error
        result = {"mode": "overleaf_online", "run_id": run_id, "status": status, "success": success,
                  "source_stable_before_after": stable, "source_verified_against_git": expected is not None and before == expected and after == expected,
                  "note": "Verification compares cloud snapshots with Git blobs (CRLF normalized for known text types). It does not lock collaborators or exclude transient edits during compilation.",
                  "diagnostics": diagnostics(log), "log": log[-40000:], "log_truncated": len(log) > 40000,
                  "full_log": str(target / "output.log") if "output.log" in downloaded else None,
                  "pdf": str(target / "output.pdf") if success else None}
        (target / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
