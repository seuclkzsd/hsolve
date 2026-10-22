import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p38');repo=Path('/tmp/os2026-p10-repair.9doyhO')
for name in ['diagnostic-guard.json','full-guard.json']:
 assert json.loads((p/name).read_text())['returncode']==0,name
assert json.loads((p/'full-adaptive/summary.json').read_text())['success']
assert json.loads((p/'diagnostic-qualified.json').read_text())['qualified']
subprocess.run(['python','-I',str(p/'verify_contracts.py')],check=True)
assert not (p/'screen-monitor-result.json').exists()
with (p/'monitor-driver.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','-u',str(p/'monitored_screen.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(r.returncode)
