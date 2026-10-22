import hashlib,json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p40/v3');repo=Path('/tmp/os2026-p10-repair.9doyhO')
for name in ['build-guard.json','linear-guard.json','boundary-v3-guard.json','diagnostic-guard.json','full-guard.json']:
 assert json.loads((p/name).read_text())['returncode']==0,name
for variant in ['control','enclosed']:
 assert json.loads((p/('full-'+variant)/'summary.json').read_text())['success']
for name in ['enclosure-qualified.json','boundary-qualified.json','diagnostic-qualified.json']:
 assert json.loads((p/name).read_text())['qualified'],name
assert all(r['qualified'] for r in json.loads((p/'assembly-check-results.json').read_text()))
assert len(json.loads((p/'contract-check-results.json').read_text()))==18
cases=['syn-zero-cluster-complex-1e4','syn-multiplicity-complex-1e4','syn-near-singular-complex-1e4','syn-wide-range-complex-1e4','syn-near-singular-complex-1e5','syn-ghep-zero-cluster-complex-1e4','yee-photonic-rods-1e4','yee-photonic-spheres-1e4','yee-bloch-1e4']
solvers=['hsolve-base','hsolve-native','hsolve-dd','hsolve-control','hsolve-enclosed','slepc']
remaining=list(cases);qualified={};batches=[]
# Fixed retry policy: at most four full batches, only for unqualified cases.
# Choose the first qualified full 30-run group, never a faster individual run.
for number in range(4):
 if not remaining:break
 tag='p40-candidate-r'+str(number);directory=p/('candidate-r'+str(number));assert not directory.exists();directory.mkdir()
 command=['python','-u',str(p/'candidate_compare.py'),'--solvers',','.join(solvers),'--reps','5','--timeout','120','--cores','16-31','--mem-gb','32','--root','/share/home/linzihan/os2026/data','--slepc-profile','best','--slepc-profile-file','/tmp/os2026-p34/slepc-profiles.json','--tag',tag,'--out-dir',str(directory)]+remaining
 plan=dict(tag=tag,directory=str(directory),cases=list(remaining),solvers=solvers,expected=len(remaining)*30,command=command,selection='First qualified full case group; retries only for incomplete/contaminated groups.',source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['candidate_compare.py','candidate_monitor.py','hsolve-control','hsolve-enclosed','hsolve-base','hsolve-native','hsolve-dd']})
 planfile=directory/'plan.json';planfile.write_text(json.dumps(plan,indent=2)+'\n')
 with (directory/'monitor-driver.log').open('w') as log:
  result=subprocess.run(['env/run.sh','python','-u',str(p/'candidate_monitor.py'),str(planfile)],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
 monitor=json.loads((directory/'screen-monitor-result.json').read_text());valid=[]
 for case in remaining:
  rows=[r for r in monitor.get('rows',[]) if r['case']==case]
  if len(rows)==30 and all(r['performance_usable'] for r in rows):qualified[case]=tag;valid.append(case)
 batches.append(dict(tag=tag,returncode=result.returncode,qualified=valid,monitor=str(directory/'screen-monitor-result.json')))
 remaining=[c for c in remaining if c not in qualified]
 state=dict(qualified=qualified,remaining=remaining,batches=batches,complete=not remaining)
 (p/'candidate-series.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
 if result.returncode!=0:break
