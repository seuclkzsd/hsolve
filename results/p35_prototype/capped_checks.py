import json,os,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p35')
for budget in [.4,.8]:
 env=dict(os.environ,P35_MEMORY_BUDGET_GB=str(budget))
 subprocess.run(['python','-u',str(p/'compare_capped.py'),'--solvers','hsolve-capped,hsolve-cappednative','--reps','1','--timeout','60','--cores','8-15','--mem-gb','12','--root',str(p/'large-data'),'--tag','p35-capped-large-'+str(budget).replace('.','p'),'--out-dir',str(p)]+json.loads((p/'large-inputs.json').read_text()),env=env,check=True)
