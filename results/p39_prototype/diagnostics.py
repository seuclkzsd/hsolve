import json,subprocess,os
from pathlib import Path
p=Path('/tmp/os2026-p39');old=Path('/tmp/os2026-p34');p38=Path('/tmp/os2026-p38')
new='hsolve-control,hsolve-direct,hsolve-reuse';pair='hsolve-direct,hsolve-reuse'
groups=[(p/'data','p39-new',[r['case'] for r in json.loads((p/'case-manifest.json').read_text())],60,None,new),
 (p38/'data','p39-cases',[r['case'] for r in json.loads((p38/'case-manifest.json').read_text())],60,None,new),
 (Path('/tmp/os2026-p33/accepted-data'),'p39-stress',['accepted-hep-small','accepted-hep-large','accepted-ghep-small','accepted-ghep-large'],30,None,pair)]
for group in ['holdout','fresh','validation']:
 groups.append((old/(group+'-data'),'p39-'+group,json.loads((old/(group+'-inputs.json')).read_text()),30,None,pair))
groups.append((Path('/tmp/os2026-p33/contract-data-v2'),'p39-contracts',['exact-zero-hep','exact-quarter-ghep','new-cluster-hep','new-near-hep','new-cluster-ghep','counter-fallback-memory','counter-fallback-factor','counter-fallback-allocation','backend-result-recovery'],60,None,pair))
groups.append((Path('/share/home/linzihan/os2026/data'),'p39-main',['syn-zero-cluster-complex-1e4','syn-multiplicity-complex-1e4','syn-near-singular-complex-1e4','syn-wide-range-complex-1e4','syn-near-singular-complex-1e5','syn-ghep-zero-cluster-complex-1e4','yee-photonic-rods-1e4','yee-photonic-spheres-1e4','yee-bloch-1e4'],120,None,pair))
groups.append((Path('/tmp/os2026-p35/large-data'),'p39-large',['large-complex-hep','large-complex-ghep'],60,.8,pair))
for root,tag,cases,timeout,budget,solvers in groups:
 env=dict(os.environ)
 if budget is not None:env['P39_MEMORY_BUDGET_GB']=str(budget)
 subprocess.run(['python','-u',str(p/'compare.py'),'--solvers',solvers,'--reps','1','--timeout',str(timeout),'--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,env=env,check=True)
rows=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines() if '/p39-smoke/' not in json.loads(s)['out']]
expected={r['case']:r['expected_candidate'] for base in [p,p38] for r in json.loads((base/'case-manifest.json').read_text())}
for row in rows:
 if row['case'] in expected and row['solver']!='hsolve-control':assert row.get('candidate_source')==expected[row['case']],(row['case'],row['solver'],row.get('candidate_source'))
summary=dict(attempts=len(rows),valid=sum(bool(r['valid']) for r in rows),qualified=len(rows)==205 and all(r['valid'] for r in rows))
(p/'diagnostic-qualified.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
raise SystemExit(0 if summary['qualified'] else 1)
