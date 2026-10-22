import subprocess
from pathlib import Path
p=Path('/tmp/os2026-p34');repo=Path('/tmp/os2026-p10-repair.9doyhO')
with (p/'accepted.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','tools/run/guard.py','--skip-busy-check','--cores','8-15','--mem-gb','12','--timeout','1200','--summary',str(p/'accepted-guard.json'),'--','bash',str(p/'accepted.sh')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
if r.returncode:raise SystemExit(r.returncode)
raise SystemExit(subprocess.run(['env/run.sh','python','-u',str(p/'monitored_screen_actual.py')],cwd=repo).returncode)
