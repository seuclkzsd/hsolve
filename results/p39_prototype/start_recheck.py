import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p39');repo=Path('/tmp/os2026-p10-repair.9doyhO')
m=json.loads((p/'collected.json').read_text())
expected={'syn-multiplicity-complex-1e4','syn-ghep-zero-cluster-complex-1e4','yee-bloch-1e4'}
assert {case for case,ok in m['qualified_cases'].items() if not ok}==expected
assert json.loads((p/'screen-monitor-result.json').read_text())['returncode']==0
assert not (p/'recheck/screen-monitor-result.json').exists()
with (p/'recheck-driver.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','-u',str(p/'recheck_monitor.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(r.returncode)
