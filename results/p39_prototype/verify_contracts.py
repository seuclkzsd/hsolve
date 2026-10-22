import json
from pathlib import Path
p=Path('/tmp/os2026-p39');raw=Path('/tmp/os2026-p10-repair.9doyhO/results/raw/p39-contracts');items=json.loads((Path('/tmp/os2026-p33')/'contract-inputs.json').read_text());results=[]
summary=json.loads((p/'p39-contracts.json').read_text())
assert all(x['ok'] and x['completeness']==['complete'] for row in summary['rows'] for x in row['solvers'].values())
for item in items:
 for solver in ['hsolve-direct','hsolve-reuse']:
  events=[json.loads(x) for x in (raw/item['case']/('events-'+solver+'.jsonl')).read_text().splitlines()]
  assert any(x.get('event')=='factor_backend' for x in events),(item,solver,'private backend not used')
  probes=[x for x in events if x.get('event')=='checked_requested_shift']
  rep=json.loads((raw/item['case']/solver/'report.json').read_text())
  if 'expected_probe' in item:assert probes and probes[0]['accepted']==item['expected_probe'],(item,solver,probes)
  if item.get('expected_moved'):assert rep['sigma_used']!=rep['sigma_requested'],(item,solver,rep['sigma_used'])
  recovery=[x for x in events if x.get('event')=='private_backend_fallback']
  if item.get('expected_recovery'):assert len(recovery)==1,(item,solver,recovery)
  counter=any(x.get('event')=='inertia_counter' for x in events)
  if item['expected_counter']:assert counter,(item,solver)
  results.append(dict(case=item['case'],solver=solver,probe_events=probes,recovery_events=recovery,counter_used=counter,sigma_requested=rep['sigma_requested'],sigma_used=rep['sigma_used'],certificate_passed=rep['certificate']['passed']))
(p/'contract-check-results.json').write_text(json.dumps(results,indent=2)+'\n');print('Verified',len(results),'private-backend full-solve contract results',flush=True)
