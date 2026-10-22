import json
from pathlib import Path
p=Path('/tmp/os2026-p33');checks=[]
for tag,total in [('p33-diagnostic-v2',18),('p33-contracts-v2',27),('p33-recovery-error',1),('p33-recovery-incomplete',1)]:
 s=json.loads((p/(tag+'.json')).read_text());rows=[x for row in s['rows'] for x in row['solvers'].values()]
 assert sum(x['reps'] for x in rows)==total
 assert all(x['ok'] and x['completeness']==['complete'] for x in rows),(tag,rows)
 checks.append(dict(tag=tag,valid=total,complete=total))
assert len(json.loads((p/'contract-check-results.json').read_text()))==18
assert len(json.loads((p/'recovery-results.json').read_text()))==2
for v in ['requested','requestedlu']:
 rows=json.loads((p/(v+'-check-results.json')).read_text());assert len(rows)==1540 and all(x['valid'] for x in rows)
print(json.dumps(dict(qualified=True,full_solve_batches=checks,linear_checks=3080)),flush=True)
(p/'correctness-qualified.json').write_text(json.dumps(dict(qualified=True,full_solve_batches=checks,linear_checks=3080),indent=2)+'\n')
