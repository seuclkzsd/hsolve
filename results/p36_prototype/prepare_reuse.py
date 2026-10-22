import json
from pathlib import Path
p=Path('/tmp/os2026-p36');dest=p/'check-reuse';dest.mkdir(exist_ok=True)
rows=json.loads(Path('/tmp/os2026-p33/requested-manifest.json').read_text())
items=[{**x,'prefix':str(dest/(x['id']+'-result'))} for x in rows]
(p/'reuse-manifest.json').write_text(json.dumps(items,indent=2)+'\n')
