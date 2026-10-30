"""Export/import portable project metadata, never cookies, credentials or source."""
import json
import re
from pathlib import Path


def export(config, destination):
    path = Path(destination).expanduser()
    if path.exists():
        raise ValueError('Export destination exists')
    path.write_text(json.dumps({'format': 1, 'online_project_id': config['online_project_id']}, indent=2), encoding='utf-8')
    return str(path)


def read(source):
    value = json.loads(Path(source).expanduser().read_text(encoding='utf-8'))
    if value.get('format') != 1 or not re.fullmatch('[a-fA-F0-9]{24}', value.get('online_project_id', '')):
        raise ValueError('Invalid migration manifest')
    return value['online_project_id']
