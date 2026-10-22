import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p35');old=Path('/tmp/os2026-p34')
groups=[(Path('/tmp/os2026-p33/accepted-data'),'p35-stress',['accepted-hep-small','accepted-hep-large','accepted-ghep-small','accepted-ghep-large'])]
for group in ['holdout','fresh','validation']:
 groups.append((old/(group+'-data'),'p35-'+group,json.loads((old/(group+'-inputs.json')).read_text())))
for root,tag,cases in groups:
 subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-packed,hsolve-packednative','--reps','1','--timeout','30','--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,check=True)
