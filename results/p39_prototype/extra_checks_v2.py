import json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.eval import common
common.require_guard('P39 retain perturbed factor shift across expansion')
p=Path('/tmp/os2026-p39');root=p/'data'
# Seven sectors initially provide fourteen pairs. Asking for all fourteen sets
# the radius to their farthest value, forcing every sector to expand. k=14 also
# respects the recognizer guard blocks>=2*k+4 (32>=32). The initial k=20 test
# correctly fell back before sector construction; retain its failure record.
c=cio.load_case('target-on-mode',root=root)
cfg=dict(c.config);cfg['target']=dict(cfg['target'],k=14)
name='target-on-mode-expansion-v2'
cio.save_case(name,c.A,c.B,meta=dict(family='p39-validation',problem='HEP'),config=cfg,root=root)
ref=cio.load_ref(c.name,root=root)
cio.save_ref(name,ref.eigenvalues,kind='dense',complete=True,note='Same original matrix as target-on-mode; independent complete small dense reference retained.',root=root)
(p/'extra-case-manifest-v2.json').write_text(json.dumps([dict(case=name,n=c.A.shape[0],expected_candidate='partial_bloch_translation')],indent=2)+'\n')
subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-control,hsolve-direct,hsolve-reuse','--reps','1','--timeout','60','--cores','8-15','--mem-gb','12','--root',str(root),'--tag','p39-extra-v2','--out-dir',str(p),name],check=True)
rows=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines() if '/p39-extra-v2/' in json.loads(s)['out']]
assert len(rows)==3 and all(r['valid'] and r['completeness']=='complete' for r in rows),rows
row=next(r for r in rows if r['solver']=='hsolve-reuse')
assert row['candidate_source']=='partial_bloch_translation',row
out=Path(row['out']);log=out.parent/('guard-'+out.name+'.stderr.txt')
pattern=r'P39 sector mode=(\d+).*?reused=(\d+) analyses=(\d+) factors=(\d+) rhs=(\d+) shift=([0-9.e+-]+)'
sectors=[]
for a in re.findall(pattern,log.read_text()):
 r=dict(zip(['mode','reused','analyses','factors','rhs'],map(int,a[:5])));r['shift']=float(a[5]);sectors.append(r)
requested=cfg['target']['sigma'];moved=[r for r in sectors if r['reused'] and r['shift']!=requested]
assert moved,'No perturbed shift was actually reused; this check has not exercised its contract'
for r in moved:
 first=next(s for s in sectors if s['mode']==r['mode'] and not s['reused'])
 assert r['shift']==first['shift'] and r['analyses']==r['factors']==0,(first,r)
result=dict(attempts=3,valid=3,qualified=True,requested_shift=requested,perturbed_reuse=moved,sectors=sectors)
(p/'extra-check-results-v2.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
