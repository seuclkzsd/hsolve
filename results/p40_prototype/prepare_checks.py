import json
from pathlib import Path
p=Path('/tmp/os2026-p40')
rows=json.loads(Path('/tmp/os2026-p33/requested-manifest.json').read_text())
for variant in ['control','enclosed']:
 dest=p/('check-'+variant);dest.mkdir(exist_ok=True)
 items=[{**x,'prefix':str(dest/(x['id']+'-result'))} for x in rows]
 (p/(variant+'-manifest.json')).write_text(json.dumps(items,indent=2)+'\n')
print('Prepared',len(rows),'unchanged independent inputs.',flush=True)
