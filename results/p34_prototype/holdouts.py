import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
subprocess.run(['python','-u',str(p/'prepare_holdouts.py')],check=True)
cmd=['python','-u',str(p/'compare.py'),'--solvers','hsolve-base,hsolve-guarded,hsolve-projected,hsolve-projectednative','--reps','1','--timeout','120','--cores','8-15','--mem-gb','12','--root',str(p/'holdout-data'),'--tag','p34-holdouts','--out-dir',str(p)]+json.loads((p/'holdout-inputs.json').read_text())
subprocess.run(cmd,check=True)
