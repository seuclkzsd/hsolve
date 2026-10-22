import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
cases=['fresh-01-blocks-real-hep','fresh-03-blocks-real-ghep','fresh-13-coupled-complex-hep','fresh-15-coupled-complex-ghep']
for ranks in [1,4,8]:
 profiles=dict(schema_version=1,profiles=[dict(scope='case',name=name,mode='nearest',cores=8,target=None,config=dict(ranks=ranks,threads=8//ranks,bind='core',options=dict(eps_ncv='4k',eps_tol='1e-12',eps_true_residual='1'))) for name in cases])
 f=p/f'slepc-accuracy-r{ranks}.json';f.write_text(json.dumps(profiles,indent=2)+'\n')
 subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','slepc','--slepc-profile','best','--slepc-profile-file',str(f),'--reps','1','--timeout','30','--cores','8-15','--mem-gb','12','--root',str(p/'fresh-data'),'--tag',f'p34-reference-r{ranks}','--out-dir',str(p)]+cases,check=True)
