import json,sys
from pathlib import Path
import numpy as np
from scipy import sparse,linalg
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.gen.yee import YeeGrid,make_photonic_case
from tools.eval import common
common.require_guard('P38 small independent reference cases')
p=Path('/tmp/os2026-p38');root=p/'data';manifest=[]
def save(name,a,b,expected,sigma=.7,k=6,config=None):
 n=a.shape[0];assert n<=4000
 cfg=cio.default_config(sigma,k);cfg.update(config or {})
 cio.save_case(name,a,b,meta=dict(family='p38-validation',problem='GHEP' if b is not None else 'HEP'),config=cfg,root=root)
 # Explicitly permitted small test/evaluation oracle. Solver never reads refs.
 w=linalg.eigvalsh(a.toarray(),None if b is None else b.toarray(),check_finite=True)
 cio.save_ref(name,w,kind='dense',complete=True,note='Independent full dense oracle; n<=4000 test/evaluation exception only.',root=root)
 manifest.append(dict(case=name,n=n,expected_candidate=expected))
for label,m,period,phase,bkind in [('hep',32,7,.31,'none'),('ghep',40,9,-.73,'diag'),('sparse-mass',32,5,1.17,'sparse'),('period3',36,3,np.pi,'none')]:
 rng=np.random.default_rng(3800+period);off=.15*(rng.normal(size=m-1)+1j*rng.normal(size=m-1))
 h=sparse.diags([np.conj(off),np.linspace(-3,3,m),off],[-1,0,1],format='csr')
 t=sparse.diags([np.ones(period-1)],[1],shape=(period,period),format='lil',dtype=complex);t[period-1,0]=np.exp(1j*phase);t=t.tocsr()
 lap=2*sparse.eye(period)-t-t.conj().T
 a=sparse.kron(h,sparse.eye(period))+sparse.kron(sparse.diags(np.linspace(.2,1.1,m)),lap);a=a.tocsr()
 b=None if bkind=='none' else sparse.kron(sparse.diags(np.linspace(.7,1.3,m)),sparse.eye(period)).tocsr()
 if bkind=='sparse':b=b+.03*sparse.kron(sparse.eye(m),lap)
 save('cycle-'+label,a,b,'partial_bloch_translation')
 if label=='ghep':
  bad=a.tolil();bad[2,2]+=1e-4;save('broken-a',bad.tocsr(),b,'iterative')
  badb=b.tolil();badb[2,2]*=1.01;save('broken-b',a,badb.tocsr(),'iterative')
  save('explicit-method',a,b,'iterative',config={'method':'shift_invert_lanczos'})
  save('certificate-off',a,b,'iterative',config={'certificate':'off'})
  save('missing-pair',a,b,'partial_bloch_translation',config={'certificate_fault_drop':1})
for name,cells,phase,form in [('small-rods-hep',(4,5,7),(-.4,.7,-.19),'standard'),('small-rods-ghep',(5,4,6),(.3,-.9,.47),'generalized')]:
 make_photonic_case(name,YeeGrid(cells,(1.,.8,1.2),'bloch',phase),form,'rods',.24,7.1,root)
 c=cio.load_case(name,root=root);save(name,c.A,c.B,'partial_bloch_translation',c.config['target']['sigma'],c.config['target']['k'])
(p/'case-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True)
