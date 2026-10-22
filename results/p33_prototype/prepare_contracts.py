import json,sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.gen.synthetic import write_case,target_at,spectrum_preset,prescribed_hermitian,congruence_pair,congruence_cond_bound
from tools import case
p=Path('/tmp/os2026-p33');root=p/'contract-data-v2';rows=[]
for name,sigma,general in [('exact-zero-hep',0.,False),('exact-quarter-ghep',.25,True)]:
 n=4096;w=np.r_[np.tile([sigma,sigma+2.],8),sigma-np.linspace(.04,2.,(n-16)//2),sigma+np.linspace(.05,2.1,(n-16)//2)]
 bdiag=2.**((np.arange(n)%9)-4) if general else np.ones(n)
 for j in range(8):bdiag[2*j+1]=bdiag[2*j]
 a=sp.diags(w*bdiag,dtype=np.complex128,format='lil')
 for j in range(8):
  i=2*j;mass=bdiag[i];a[i,i]=a[i+1,i+1]=(sigma+1)*mass;a[i,i+1]=1j*mass;a[i+1,i]=-1j*mass
 perm=np.random.default_rng(3302+int(general)).permutation(n)
 a=a.tocsr()[perm,:][:,perm];b=sp.diags(bdiag[perm],dtype=np.complex128,format='csr') if general else None
 w=w[perm]
 write_case(name,a,b,meta={'family':'synthetic','problem':'GHEP' if general else 'HEP','description':'P33 exactly singular complex requested shift, eight repeated eigenvalues'},targets=[target_at(w,sigma,12,'exact singular requested-shift probe rejection',cond_b=256 if general else 1)],root=root,eigenvalues=w,ref_note='Eight exact complex rank-one 2x2 blocks at sigma; remaining diagonal. Powers-of-two block masses preserve exact shifted rank deficiency.')
 rows.append(dict(case=name,expected_probe=False,expected_moved=True,expected_counter=False))
for name,n,kind,seed,bc in [('new-cluster-hep',7000,'zero-cluster',3311,None),('new-near-hep',18000,'near-singular',3312,None),('new-cluster-ghep',9000,'zero-cluster',3313,20.)]:
 spec=spectrum_preset(kind,n,seed,cond_b=congruence_cond_bound(bc) if bc else 1.)
 if bc:a,b=congruence_pair(spec.eigenvalues,b_cond=bc,bandwidth=2,block=8,complex_=True,seed=seed+1,grouping=spec.grouping)
 else:a=prescribed_hermitian(spec.eigenvalues,block=8,complex_=True,seed=seed+1,grouping=spec.grouping);b=None
 write_case(name,a,b,meta={'family':'synthetic','problem':'GHEP' if bc else 'HEP','description':'P33 independent requested-shift holdout','params':{'seed':seed,'block':8,'b_cond':bc}},targets=spec.targets,root=root,eigenvalues=spec.eigenvalues,ref_note='New P33 prescribed-spectrum input; floating-point assembly error applies.')
 rows.append(dict(case=name,expected_counter=False))
# Faults test memory, numerical and allocation failures in main counts.  They
# must use the independent MUMPS counter, which cannot cast the private backend.
src=case.load_case('new-cluster-hep',root=root);ref=case.load_ref('new-cluster-hep',root=root)
for kind,bit in [('memory',2),('factor',18),('allocation',34)]:
 name='counter-fallback-'+kind;cfg=dict(src.config);cfg['certificate_fault_count']=bit
 case.save_case(name,src.A,src.B,meta={**src.meta,'description':'P33 injected main-count failure'},config=cfg,root=root)
 # The independent full spectrum is the same as the source matrix's.
 import shutil
 dest=root/'refs'/name;dest.mkdir(parents=True,exist_ok=True)
 for f in (root/'refs'/'new-cluster-hep').iterdir():
  if f.is_file():shutil.copy2(f,dest/f.name)
 rows.append(dict(case=name,expected_counter=True,fault=bit))
# Existing rejection fault also exercises the private backend's full restart.
name='backend-result-recovery';cfg=dict(src.config);cfg['inexact_fault_reject']=True
case.save_case(name,src.A,src.B,meta={**src.meta,'description':'P33 injected private result rejection'},config=cfg,root=root)
dest=root/'refs'/name;dest.mkdir(parents=True,exist_ok=True)
for f in (root/'refs'/'new-cluster-hep').iterdir():
 if f.is_file():shutil.copy2(f,dest/f.name)
rows.append(dict(case=name,expected_counter=False,expected_recovery=True))
(p/'contract-inputs.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows),flush=True)
