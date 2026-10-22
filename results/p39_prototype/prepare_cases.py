import json,sys
from pathlib import Path
import numpy as np
from scipy import sparse,linalg
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.eval import common
common.require_guard('P39 factor reuse contract cases')
p=Path('/tmp/os2026-p39');root=p/'data';old=Path('/tmp/os2026-p38/data');manifest=[]
def save(name,a,b,config,expected):
 assert a.shape[0]<=4000
 cio.save_case(name,a,b,meta=dict(family='p39-validation',problem='GHEP' if b is not None else 'HEP'),config=config,root=root)
 w=linalg.eigvalsh(a.toarray(),None if b is None else b.toarray(),check_finite=True)
 cio.save_ref(name,w,kind='dense',complete=True,note='Independent dense reference of small test only (n<=4000).',root=root)
 manifest.append(dict(case=name,n=a.shape[0],expected_candidate=expected))
c=cio.load_case('cycle-hep',root=old);w=cio.load_ref(c.name,root=old).eigenvalues
cfg=dict(c.config);cfg['target']=dict(cfg['target'],sigma=float(w[np.argmin(abs(w-.7))]));save('target-on-mode',c.A,c.B,cfg,'partial_bloch_translation')
c=cio.load_case('cycle-ghep',root=old);cfg=dict(c.config);cfg['target']=dict(cfg['target'],k=12);save('high-k',c.A,c.B,cfg,'partial_bloch_translation')
c=cio.load_case('cycle-hep',root=old);cfg=dict(c.config,zero_filter_tol=1e-12);save('zero-filter',c.A,c.B,cfg,'iterative')
m=48;period=7;phase=.39
t=sparse.diags([np.ones(period-1)],[1],shape=(period,period),format='lil',dtype=complex);t[period-1,0]=np.exp(1j*phase);t=t.tocsr();lap=2*sparse.eye(period)-t-t.conj().T
h=sparse.diags(np.repeat(np.linspace(-3,3,m//2),2))
a=sparse.kron(h,sparse.eye(period))+sparse.kron(sparse.eye(m),lap)
save('repeated-spectrum',a.tocsr(),None,cio.default_config(.7,10),'partial_bloch_translation')
(p/'case-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True)
