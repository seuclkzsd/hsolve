import json,subprocess,os
from pathlib import Path
p=Path('/tmp/os2026-p36');old=Path('/tmp/os2026-p34')
solvers='hsolve-reuse'
groups=[(Path('/tmp/os2026-p33/accepted-data'),'p36-reuse-stress',['accepted-hep-small','accepted-hep-large','accepted-ghep-small','accepted-ghep-large'],30,None)]
for group in ['holdout','fresh','validation']:
 groups.append((old/(group+'-data'),'p36-reuse-'+group,json.loads((old/(group+'-inputs.json')).read_text()),30,None))
groups.append((Path('/tmp/os2026-p33/contract-data-v2'),'p36-reuse-contracts',['exact-zero-hep','exact-quarter-ghep','new-cluster-hep','new-near-hep','new-cluster-ghep','counter-fallback-memory','counter-fallback-factor','counter-fallback-allocation','backend-result-recovery'],60,None))
groups.append((Path('~/os2026/data'),'p36-reuse-main',['syn-zero-cluster-complex-1e4','syn-multiplicity-complex-1e4','syn-near-singular-complex-1e4','syn-wide-range-complex-1e4','syn-near-singular-complex-1e5','syn-ghep-zero-cluster-complex-1e4','yee-photonic-rods-1e4','yee-photonic-spheres-1e4','yee-bloch-1e4'],120,None))
groups.append((Path('/tmp/os2026-p35/large-data'),'p36-reuse-large',['large-complex-hep','large-complex-ghep'],60,.8))
for root,tag,cases,timeout,budget in groups:
 env=dict(os.environ)
 if budget is not None:env['P36_MEMORY_BUDGET_GB']=str(budget)
 subprocess.run(['python','-u',str(p/'compare_reuse.py'),'--solvers',solvers,'--reps','1','--timeout',str(timeout),'--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,env=env,check=True)
subprocess.run(['python',str(p/'verify_contracts_reuse.py')],check=True)
rows=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines()]
rows=[r for r in rows if '/p36-reuse-' in r['out']]
summary=dict(attempts=len(rows),valid=sum(bool(r['valid']) for r in rows),qualified=len(rows)==80 and all(r['valid'] for r in rows))
(p/'reuse-qualified.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
raise SystemExit(0 if summary['qualified'] else 1)
