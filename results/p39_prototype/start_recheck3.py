import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p39');repo=Path('/tmp/os2026-p10-repair.9doyhO')
m=json.loads((p/'recheck2/screen-monitor-result.json').read_text());assert m['returncode']==0
bad={r['case'] for r in m['rows'] if not r['performance_usable']}
assert bad=={'syn-multiplicity-complex-1e4'}
assert not (p/'recheck3/screen-monitor-result.json').exists()
with (p/'recheck3-driver.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','-u',str(p/'recheck3_monitor.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(r.returncode)
