import json,sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.gen.synthetic import write_case,target_at,prescribed_hermitian,congruence_pair,congruence_cond_bound
p=Path('/tmp/os2026-p34');root=p/'validation-data';cases=[]
for ix in range(8):
 coupled=True;complex_=bool(ix&1);general=bool(ix&2);power=8 if ix&4 else -8
 n=[3072,7168,9216][ix%3];mult=[5,9,17,25][ix%4];sigma=-.2 if general else .15;delta=2.**(-28 if ix<4 else -31);scale=2.**power
 neg=(n-2*mult)//2;pos=n-2*mult-neg
 w=np.r_[np.tile([sigma+delta,sigma+2-delta],mult),sigma-np.linspace(.04,2.,neg),sigma+np.linspace(.05,2.1,pos)]
 seed=3600+ix;name=f'validation-{ix:02d}-{ "coupled" if coupled else "blocks" }-{ "complex" if complex_ else "real" }-{ "ghep" if general else "hep" }'
 if coupled:
  if general:a,b=congruence_pair(w,b_cond=32.,bandwidth=2,block=4,complex_=complex_,seed=seed,grouping='random');cond=congruence_cond_bound(32.)
  else:a=prescribed_hermitian(w,block=4,complex_=complex_,seed=seed,grouping='random');b=None;cond=1.
 else:
  bd=2.**((np.arange(n)%7)-3) if general else np.ones(n)
  for j in range(mult):bd[2*j+1]=bd[2*j]
  a=sp.diags(w*bd,dtype=np.complex128 if complex_ else np.float64,format='lil')
  for j in range(mult):
   i=2*j;mass=bd[i];a[i,i]=a[i+1,i+1]=(sigma+1)*mass
   z=(1j if complex_ else 1.)*(1-delta)*mass;a[i,i+1]=z;a[i+1,i]=np.conj(z)
  perm=np.random.default_rng(seed).permutation(n);a=a.tocsr()[perm,:][:,perm]
  b=sp.diags(bd[perm],format='csr') if general else None;w=w[perm];cond=64. if general else 1.
 a=a*scale
 if general:b=b*scale
 else:w=w*scale;sigma*=scale
 write_case(name,a,b,meta={'family':'synthetic','problem':'GHEP' if general else 'HEP','description':'P34 independent residual-rescue stress input','params':{'seed':seed,'coupled':coupled,'multiplicity':mult,'delta':delta,'scale_power':power}},targets=[target_at(w,sigma,mult+6,'near multiplet plus separated additional eigenpairs',cond_b=cond)],root=root,eigenvalues=w,ref_note='Prescribed full spectrum; floating-point congruence/similarity assembly error for coupled cases.')
 cases.append(name)
(p/'validation-inputs.json').write_text(json.dumps(cases,indent=2)+'\n');print('Prepared',len(cases),'independent holdout inputs',flush=True)
