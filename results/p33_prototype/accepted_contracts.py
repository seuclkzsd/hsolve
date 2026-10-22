import json,sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.gen.synthetic import write_case,target_at
p=Path('/tmp/os2026-p33');root=p/'accepted-data';cases=[]
for ix,(general,power) in enumerate([(False,-12),(False,12),(True,-12),(True,12)]):
 name=f'accepted-{ "ghep" if general else "hep" }-{ "small" if power<0 else "large" }'
 n=4096;sigma=.25 if general else 0.;delta=2.**-28;scale=2.**power
 w=np.r_[np.tile([sigma+delta,sigma+2-delta],8),sigma-np.linspace(.04,2.,(n-16)//2),sigma+np.linspace(.05,2.1,(n-16)//2)]
 bd=2.**((np.arange(n)%9)-4) if general else np.ones(n)
 for j in range(8):bd[2*j+1]=bd[2*j]
 a=sp.diags(w*bd,dtype=np.complex128,format='lil')
 for j in range(8):
  i=2*j;mass=bd[i];a[i,i]=a[i+1,i+1]=(sigma+1)*mass;a[i,i+1]=1j*(1-delta)*mass;a[i+1,i]=-1j*(1-delta)*mass
 perm=np.random.default_rng(3340+ix).permutation(n)
 a=a.tocsr()[perm,:][:,perm]*scale;b=sp.diags(bd[perm]*scale,dtype=np.complex128,format='csr') if general else None
 w=w[perm] if general else w[perm]*scale
 write_case(name,a,b,meta={'family':'synthetic','problem':'GHEP' if general else 'HEP','description':'P33 nonsingular original-shift acceptance; exact binary 2x2 blocks','params':{'scale_power':power,'delta':delta,'permutation_seed':3340+ix}},targets=[target_at(w,sigma,12,'weak null-pivot rejection, original-shift acceptance branch',cond_b=256 if general else 1)],root=root,eigenvalues=w,ref_note='Exact eigenvalues of binary-valued complex 2x2 blocks and diagonal remainder. Matrix and B scaled together for GHEP.')
 cases.append(name)
(p/'accepted-inputs.json').write_text(json.dumps(cases,indent=2)+'\n');print(cases,flush=True)
