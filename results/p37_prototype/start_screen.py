import hashlib,json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p37');repo=Path('/tmp/os2026-p10-repair.9doyhO')
for name in ['diagnostic-guard.json','full-guard.json','residual-v2-guard.json','boundary-v2-guard.json']:
 assert json.loads((p/name).read_text())['returncode']==0,name
for v in ['scalar','dd']:
 r=json.loads((p/f'full-{v}/summary.json').read_text());assert r['success'] and r['invocations']==71
assert json.loads((p/'diagnostic-qualified.json').read_text())['qualified']
q=json.loads((p/'boundary-qualified-v2.json').read_text());assert q['checks']==q['valid']==320 and q['decimal_checks']==q['decimal_valid']==1296
hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ['boundary_check.cpp','boundary_check.cpp.o','boundary-check','band_backend.hpp','band_ldlh.cpp']}
(p/'boundary-build-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
assert not (p/'screen-monitor-result.json').exists()
with (p/'monitor-driver.log').open('w') as log:
 r=subprocess.run(['env/run.sh','python','-u',str(p/'monitored_screen.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(r.returncode)
