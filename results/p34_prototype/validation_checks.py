import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-base,hsolve-accepted,hsolve-acceptednative,slepc','--reps','1','--timeout','30','--cores','8-15','--mem-gb','12','--root',str(p/'validation-data'),'--tag','p34-validation','--out-dir',str(p)]+json.loads((p/'validation-inputs.json').read_text()),check=True)
