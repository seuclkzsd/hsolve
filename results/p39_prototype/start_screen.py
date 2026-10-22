import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p39');repo=Path('/tmp/os2026-p10-repair.9doyhO')
for name in ['diagnostic-guard.json','full-guard.json','budget-v2-guard.json','extra-v2-guard.json']:
 assert json.loads((p/name).read_text())['returncode']==0,name
for variant in ['direct','reuse']:
 assert json.loads((p/('full-'+variant)/'summary.json').read_text())['success']
assert json.loads((p/'diagnostic-qualified.json').read_text())['qualified']
assert len(json.loads((p/'budget-check-results.json').read_text())['profiles'])==4
subprocess.run(['python','-I',str(p/'verify_contracts.py')],check=True)
assert json.loads((p/'extra-check-results-v2.json').read_text())['qualified']
assert not (p/'screen-monitor-result.json').exists()
with (p/'monitor-driver.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','-u',str(p/'monitored_screen.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(r.returncode)
