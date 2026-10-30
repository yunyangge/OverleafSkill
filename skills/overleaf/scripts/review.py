"""Offline, escaped review snapshots. No web service or third-party resources."""
from datetime import datetime, timezone
import difflib
import hashlib
from html import escape
from itertools import zip_longest
import json
from pathlib import Path
import uuid

CSS = '''
:root{color-scheme:light;--ink:#19352f;--muted:#62736f;--line:#dce5e1}
*{box-sizing:border-box}body{margin:0;background:#f5f8f6;color:var(--ink);font:15px system-ui,sans-serif}
header{padding:32px max(24px,4vw);background:#143e34;color:#fff}h1{margin:8px 0;font-size:30px}
header p{color:#d6e5de;max-width:1000px;overflow-wrap:anywhere}.brand{letter-spacing:2px;font-size:12px}
.layout{padding:24px 4vw}nav{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
a{color:#17664d}nav a,.download{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;text-decoration:none}
label{cursor:pointer;margin:8px}details{border:1px solid var(--line);border-radius:12px;background:white;margin:20px 0;overflow:hidden}
summary{padding:18px;cursor:pointer;font-weight:600;overflow-wrap:anywhere}.meta{padding:0 18px 14px;color:var(--muted);overflow-wrap:anywhere;font:12px ui-monospace,monospace}
.technical{border:0;border-radius:0;margin:0}.technical summary{font-size:12px;font-weight:400;padding:0 18px 8px;color:var(--muted)}.snapshots{padding:0 18px;margin:4px 0 12px;font-size:13px}
.scroll{overflow-x:auto}table{width:100%;min-width:700px;table-layout:fixed;border-collapse:collapse;font:13px/1.6 ui-monospace,Consolas,monospace}
th{background:#edf2ef;padding:9px;text-align:left}td{vertical-align:top;border-top:1px solid #edf0ee;padding:3px 8px}
.ln{width:50px;color:#75877e;text-align:right;user-select:none}.code{white-space:pre-wrap;overflow-wrap:anywhere}
.del{background:#ffebe9;color:#762a28}.add{background:#e4f6e9;color:#175335}.word{font-weight:bold;text-decoration:underline;text-decoration-thickness:2px}
.gap td{background:#eff4f1;color:#62736f;padding:9px}.note{padding:18px;color:var(--muted)}
#only:checked ~ main tr.context{display:none}footer{padding:20px 0;color:var(--muted);font-size:13px}
'''


def fingerprint(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def text_lines(data):
    if data is None:
        return []
    if b'\0' in data:
        return None
    try:
        return data.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        return None


def marked(left, right):
    if len(left) + len(right) > 2000:
        return escape(left), escape(right)
    a, b = [], []
    for tag, i, j, k, l in difflib.SequenceMatcher(None, left, right).get_opcodes():
        x, y = escape(left[i:j]), escape(right[k:l])
        a.append(x if tag == 'equal' else '<span class="word">' + x + '</span>')
        b.append(y if tag == 'equal' else '<span class="word">' + y + '</span>')
    return ''.join(a), ''.join(b)


def table(left, right):
    matcher = difflib.SequenceMatcher(None, left, right)
    added = removed = 0
    for tag, i, j, k, l in matcher.get_opcodes():
        if tag != 'equal':
            added += l-k
            removed += j-i
    rows = ['<table><colgroup><col class="ln"><col><col class="ln"><col></colgroup><thead><tr><th colspan="2">修改前 / Before</th><th colspan="2">修改后 / After</th></tr></thead><tbody>']
    for group in matcher.get_grouped_opcodes(3):
        rows.append('<tr class="gap"><td colspan="4">… 上下文 / Context …</td></tr>')
        for tag, i, j, k, l in group:
            for old, new in zip_longest(range(i,j), range(k,l)):
                a, b = left[old] if old is not None else '', right[new] if new is not None else ''
                a, b = marked(a,b) if tag == 'replace' else (escape(a),escape(b))
                cls = 'context' if tag == 'equal' else 'changed'
                x = 'del' if tag != 'equal' and old is not None else ''
                y = 'add' if tag != 'equal' and new is not None else ''
                rows.append(f'<tr class="{cls}"><td class="ln {x}">{old+1 if old is not None else ""}</td><td class="code {x}">{a}</td><td class="ln {y}">{new+1 if new is not None else ""}</td><td class="code {y}">{b}</td></tr>')
    rows.append('</tbody></table>')
    if not added and not removed:
        rows.append('<p class="note">文本行相同；文件字节、换行或文件存在状态可能不同。Text lines match; inspect byte hashes and snapshots.</p>')
    return ''.join(rows), added, removed


def create(root, before, after, scope, review_id=None, raw_diff=None):
    folder = Path(root) / '.git/overleaf-reviews' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    files, sections, navigation, unified = [], [], [], []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        number = len(files)
        status = 'created' if old is None else 'deleted' if new is None else 'modified'
        item = {'file':name,'status':status,'before_sha256':fingerprint(old),'after_sha256':fingerprint(new),
                'before_bytes':len(old or b''),'after_bytes':len(new or b''),'added':None,'removed':None}
        a, b = text_lines(old), text_lines(new)
        text = a is not None and b is not None
        label = escape(name)
        body = ''
        if text:
            links = []
            for side, value in (('before',old),('after',new)):
                if value is not None:
                    filename = f'{number}-{side}.txt'
                    (folder/filename).write_bytes(value)
                    links.append(f'<a href="{filename}" download>{side}.txt</a>')
            body += '<p class="snapshots">' + ' · '.join(links) + '</p>'
            # Avoid expensive line/character matching on huge assets or pathological input.
            if len(old or b'') + len(new or b'') <= 200_000 and len(a)+len(b) <= 2000:
                rendered, added, removed = table(a,b)
                item.update(added=added,removed=removed)
                body += '<div class="scroll">' + rendered + '</div>'
                unified.extend(difflib.unified_diff(a,b,fromfile='before/'+name,tofile='after/'+name,lineterm=''))
            else:
                body += '<p class="note">大文件：请下载前后文本查看，未渲染行级差异。Large file: inspect the before/after snapshots.</p>'
                unified.append('Large text omitted from rendered diff: ' + name)
        else:
            body = '<p class="note">二进制资源：显示大小与 SHA-256，不渲染源码。Binary asset: compare size and hash; no textual diff.</p>'
            unified.append('Binary file changed: ' + name)
        count = f'+{item["added"]} / −{item["removed"]}' if item['added'] is not None else 'asset / large file'
        navigation.append(f'<a href="#file-{number}">{label} · {count}</a>')
        meta = f'{item["before_bytes"]} → {item["after_bytes"]} bytes<br>Before SHA-256: {item["before_sha256"] or "absent"}<br>After SHA-256: {item["after_sha256"] or "absent"}'
        sections.append(f'<details open id="file-{number}"><summary>{label} · {status} · {count}</summary><details class="technical"><summary>版本信息 / Version details</summary><div class="meta">{meta}</div></details>{body}</details>')
        files.append(item)
    report = {'scope':scope,'created_at':datetime.now(timezone.utc).isoformat(),'review_id':review_id,
              'html':str(folder/'index.html'),'diff_file':str(folder/'changes.diff'),'files':files}
    (folder/'changes.diff').write_text(raw_diff if raw_diff is not None else '\n'.join(unified)+'\n',encoding='utf-8')
    (folder/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    subtitle = '本次操作 / This operation' if scope == 'operation' else '全部未提交修改，相对 HEAD / All uncommitted changes versus HEAD'
    html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><title>OverleafSkill · 修改审阅</title><style>'+CSS+'</style></head><body>'
    html += '<header><div class="brand">OVERLEAFSKILL / CHANGE REVIEW</div><h1>修改审阅 · '+str(len(files))+' 个文件</h1><p>'+subtitle+'</p><p>'+escape(report['created_at'])+' · 静态快照 / Saved snapshot</p></header><div class="layout">'
    if review_id:
        html += '<details class="technical"><summary>审阅版本 / Review version</summary><p class="meta">'+escape(review_id)+'</p></details>'
    html += '<a class="download" href="changes.diff" download>下载 Diff / Download</a><nav>'+''.join(navigation)+'</nav><input id="only" type="checkbox"><label for="only">只看改动行 / Changed lines only</label><main>'
    html += ''.join(sections) or '<p class="note">没有未提交修改 / No changes.</p>'
    html += '</main><footer>红色 − 删除，绿色 + 新增；下划线标出行内变化。Red: removed · Green: added · Underlined: changed text.<br>快照不会随文件修改刷新；发布前请获取新的 show_diff。Snapshot does not refresh; obtain a fresh show_diff before publishing.<br>仅保存在本机，不加载外部资源。Local only, no external resources.</footer></div></body></html>'
    (folder/'index.html').write_text(html,encoding='utf-8')
    return report


def safe_create(*args, **kwargs):
    try:
        return create(*args, **kwargs)
    except Exception:
        return {'error':'Preview unavailable. The edit result is unchanged; use show_diff or inspect Git locally. Do not repeat an edit to retry preview generation.'}
