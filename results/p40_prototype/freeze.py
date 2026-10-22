import hashlib,json,shutil
from pathlib import Path
p=Path('/tmp/os2026-p40');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
files={'hsolve-dd':Path('/tmp/os2026-p37/hsolve-dd'),'hsolve-reuse':Path('/tmp/os2026-p39/hsolve-reuse')}
for name,src in files.items():
 assert not (p/name).exists();shutil.copy2(src,p/name);assert digest(p/name)==digest(src)
record=dict(experimental={name:dict(source=str(src),sha256=digest(src)) for name,src in files.items()},production={name:digest(repo/'build/release'/name) for name in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']},sources={name:digest(p/name) for name in ['compare.py','screen.sh','monitored_screen.py']})
(p/'frozen-hashes.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
