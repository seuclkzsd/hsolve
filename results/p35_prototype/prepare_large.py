import json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.gen.synthetic import write_case,target_at,prescribed_hermitian,congruence_pair,congruence_cond_bound
p=Path('/tmp/os2026-p35');root=p/'large-data';cases=[]
for general in [False,True]:
 n=65536;mult=24;sigma=-.375 if general else .125;delta=2.**-30
 neg=(n-2*mult)//2;pos=n-2*mult-neg
 w=np.r_[np.tile([sigma+delta,sigma+2-delta],mult),sigma-np.linspace(.04,2.,neg),sigma+np.linspace(.05,2.1,pos)]
 seed=35300+int(general);name='large-complex-'+('ghep' if general else 'hep')
 if general:a,b=congruence_pair(w,b_cond=32.,bandwidth=2,block=4,complex_=True,seed=seed,grouping='random');cond=congruence_cond_bound(32.)
 else:a=prescribed_hermitian(w,block=4,complex_=True,seed=seed,grouping='random');b=None;cond=1.
 write_case(name,a,b,meta={'family':'synthetic','problem':'GHEP' if general else 'HEP','description':'P35 larger storage-budget stress input','params':{'seed':seed,'multiplicity':mult,'delta':delta}},targets=[target_at(w,sigma,mult+4,'near multiplet and four separated pairs',cond_b=cond)],root=root,eigenvalues=w,ref_note='Prescribed full spectrum, subject to floating-point similarity/congruence assembly error.')
 cases.append(name)
(p/'large-inputs.json').write_text(json.dumps(cases,indent=2)+'\n')
