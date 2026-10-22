import json
from pathlib import Path
p=Path('/tmp/os2026-p35')
rows=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines()]
rows=[r for r in rows if '/p35-capped-large-' in r['out']]
summary=dict(attempts=len(rows),valid=sum(bool(r['valid']) for r in rows),proceed=len(rows)==8 and all(r['valid'] for r in rows))
(p/'capped-gate.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
raise SystemExit(0 if summary['proceed'] else 1)
