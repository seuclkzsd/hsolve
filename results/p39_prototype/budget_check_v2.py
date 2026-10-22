import hashlib,json,shlex,subprocess,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.eval import common,evaluate
common.require_guard('P39 budget and caller thread contract')
p=Path('/tmp/os2026-p39');repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release'
commands=json.loads((p/'reuse-build-commands.json').read_text());compile=commands[0].copy();obj=p/'budget_check.cpp.o'
for opt,val in [('-c',p/'budget_check.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:compile[compile.index(opt)+1]=str(val)
# Use the single-main benchmark link recipe; CLI has separate main/argument
# parsing/hook objects. The initial verifier incorrectly assumed one CLI object.
link=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands','bench_factspeed_factor'],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
if link[:2]==[':','&&']:assert link[-2:]==['&&',':'];link=link[2:-2]
objects=[x for x in link if x.endswith('.cpp.o')];assert len(objects)==1
link=[str(obj) if x in objects else str(p/'libhsolve-reuse.a') if x=='libhsolve.a' else x for x in link];link[link.index('-o')+1]=str(p/'budget-check')
link=['-Wl,--dependency-file='+str(p/'budget-check-link.d') if x.startswith('-Wl,--dependency-file=') else x for x in link]
(p/'budget-build-commands.json').write_text(json.dumps([compile,link],indent=2)+'\n')
for cmd in [compile,link]:subprocess.run(cmd,cwd=b,check=True)
with (p/'budget-check.stdout').open('w') as out,(p/'budget-check.stderr').open('w') as err:subprocess.run([str(p/'budget-check')],stdout=out,stderr=err,check=True)
rows=json.loads((p/'budget-check.stdout').read_text());assert len(rows)==4
c=cio.load_case('cycle-ghep',root='/tmp/os2026-p38/data');w=np.load(p/'budget-eigenvalues.npy');x=np.load(p/'budget-eigenvectors.npy');norms=evaluate.estimate_norms(c.A,c.B)
metrics=evaluate.pair_metrics(c.A,c.B,w,x,norms,common.tol(c));eta=max(r['backward_error'] for r in metrics);orth=float(np.linalg.norm(x.conj().T@(c.B@x)-np.eye(len(w)),2))
ref=cio.load_ref(c.name,root='/tmp/os2026-p38/data').eigenvalues;selected=ref[np.argsort(abs(ref-c.config['target']['sigma']))[:len(w)]];err=float(np.max(abs(np.sort(w)-np.sort(selected)))/(norms.scale+max(abs(selected))))
assert len(w)==6 and eta<=1e-10 and orth<=1e-8 and err<=1e-10,(eta,orth,err)
result=dict(profiles=rows,pairs=len(w),max_eta=eta,b_orthogonality=orth,reference_set_error=err,hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ['budget_check.cpp','budget_check.cpp.o','budget-check','cached_candidates.inc','cycle.hpp','definite.cpp']})
(p/'budget-check-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(profiles=len(rows),pairs=len(w),max_eta=eta,b_orthogonality=orth,reference_set_error=err)),flush=True)
