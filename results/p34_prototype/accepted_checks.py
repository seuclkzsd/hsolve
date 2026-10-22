import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
def run(root,tag,cases,solvers):
 subprocess.run(['python','-u',str(p/'compare.py'),'--solvers',solvers,'--reps','1','--timeout','30','--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,check=True)
run(Path('/tmp/os2026-p33/accepted-data'),'p34-accepted-stress',['accepted-hep-small','accepted-hep-large','accepted-ghep-small','accepted-ghep-large'],'hsolve-accepted,hsolve-acceptednative')
run(p/'holdout-data','p34-accepted-holdouts',json.loads((p/'holdout-inputs.json').read_text()),'hsolve-accepted,hsolve-acceptednative')
run(p/'fresh-data','p34-accepted-fresh',json.loads((p/'fresh-inputs.json').read_text()),'hsolve-accepted,hsolve-acceptednative')
