import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34')
subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-base,hsolve-carried,hsolve-carriednative,slepc','--reps','1','--timeout','120','--cores','8-15','--mem-gb','12','--root',str(p/'fresh-data'),'--tag','p34-fresh','--out-dir',str(p)]+json.loads((p/'fresh-inputs.json').read_text()),check=True)
