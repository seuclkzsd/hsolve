import json,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p40/v3');b=Path('/tmp/os2026-p10-repair.9doyhO/build/release')
commands=json.loads((p/'enclosed-build-commands.json').read_text());compile=commands[0].copy();obj=p/'boundary_check.cpp.o'
for opt,val in [('-c',p/'boundary_check.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:compile[compile.index(opt)+1]=str(val)
link=commands[-1].copy();objects=[x for x in link if x.endswith('.cpp.o')];assert len(objects)==1
link=[str(obj) if x in objects else x for x in link];link[link.index('-o')+1]=str(p/'boundary-check')
link=['-Wl,--dependency-file='+str(p/'boundary-link.d') if x.startswith('-Wl,--dependency-file=') else x for x in link]
(p/'boundary-build-commands.json').write_text(json.dumps([compile,link],indent=2)+'\n')
for cmd in [compile,link]:subprocess.run(cmd,cwd=b,check=True)
dest=p/'boundary';dest.mkdir(exist_ok=True)
items=json.loads(Path('/tmp/os2026-p37/boundary-manifest.json').read_text())
items=[{**r,'prefix':str(dest/r['id'])} for r in items]
(p/'boundary-manifest.json').write_text(json.dumps(items,indent=2)+'\n')
with (p/'boundary-check.stdout').open('w') as out,(p/'boundary-check.stderr').open('w') as err:
 subprocess.run([str(p/'boundary-check'),str(p/'boundary-manifest.json')],stdout=out,stderr=err,check=True)
