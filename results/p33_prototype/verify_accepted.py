import json
from pathlib import Path
p=Path('/tmp/os2026-p33');raw=Path('/tmp/os2026-p10-repair.9doyhO/results/raw/p33-accepted-contracts');results=[]
s=json.loads((p/'p33-accepted-contracts.json').read_text())
assert all(x['ok'] and x['completeness']==['complete'] for row in s['rows'] for x in row['solvers'].values())
for name in json.loads((p/'accepted-inputs.json').read_text()):
 for solver in ['hsolve-requested','hsolve-requestedlu']:
  events=[json.loads(x) for x in (raw/name/('events-'+solver+'.jsonl')).read_text().splitlines()]
  probes=[x for x in events if x.get('event')=='checked_requested_shift']
  rep=json.loads((raw/name/solver/'report.json').read_text())
  assert len(probes)==1 and probes[0]['accepted'],(name,solver,probes)
  assert not any(x.get('event')=='private_backend_fallback' for x in events)
  assert rep['sigma_used']==rep['sigma_requested'] and rep['certificate']['passed']
  results.append(dict(case=name,solver=solver,probe=probes[0],sigma_used=rep['sigma_used'],certificate_passed=True))
(p/'accepted-contract-results.json').write_text(json.dumps(results,indent=2)+'\n');print('Verified',len(results),'accepted original-shift contracts',flush=True)
