import json
from pathlib import Path
p=Path('/tmp/os2026-p33');raw=Path('/tmp/os2026-p10-repair.9doyhO/results/raw');out=[]
for tag,case,solver,reason in [('p33-recovery-error','syn-near-singular-complex-1e4','hsolve-recovery','singular'),('p33-recovery-incomplete','syn-near-singular-complex-1e5','hsolve-recoverylu','not accepted')]:
 summary=json.loads((p/(tag+'.json')).read_text());row=summary['rows'][0]['solvers'][solver]
 assert row['ok'] and row['completeness']==['complete'],row
 events=[json.loads(x) for x in (raw/tag/case/('events-'+solver+'.jsonl')).read_text().splitlines()]
 fallback=[x for x in events if x.get('event')=='private_backend_fallback']
 assert len(fallback)==1 and reason in fallback[0]['reason'],fallback
 rep=json.loads((raw/tag/case/solver/'report.json').read_text());assert rep['certificate']['passed'] and rep['time_total_s']>fallback[0]['attempt_s']
 out.append(dict(case=case,solver=solver,fallback=fallback,total_s=rep['time_total_s'],certificate_passed=True))
(p/'recovery-results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
