import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
for root,tag,cases in [(Path('/tmp/os2026-p33/accepted-data'),'p34-shifted-stress',['accepted-hep-small','accepted-hep-large','accepted-ghep-small','accepted-ghep-large']), (p/'holdout-data','p34-shifted-holdouts',json.loads((p/'holdout-inputs.json').read_text()))]:
 subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-shifted,hsolve-shiftednative','--reps','1','--timeout','120','--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,check=True)
