import json,sys
from pathlib import Path
p=Path('/tmp/os2026-p36');mode=sys.argv[1]
if mode=='diagnostic':
 g=json.loads((p/'diagnostic-guard.json').read_text());assert g['returncode']==0 and not g.get('killed'),g
 d=json.loads((p/'diagnostic-qualified.json').read_text());assert d['qualified'],d
 for v in ['control','fused','simd']:
  checks=json.loads((p/f'{v}-check-results.json').read_text());assert len(checks)==1540 and all(r['valid'] for r in checks)
elif mode=='full':
 g=json.loads((p/'full-guard.json').read_text());assert g['returncode']==0 and not g.get('killed'),g
 for v in ['fused','simd']:
  d=json.loads((p/f'full-{v}/summary.json').read_text());assert d['success'] and d['invocations']==71,d
else:raise ValueError(mode)
print(mode,'gate passed',flush=True)

if mode=='full' and (p/'defer-screen').exists():
 print('Full regressions passed; formal comparison deferred for the factor-reuse candidate.',flush=True)
 raise SystemExit(75)
