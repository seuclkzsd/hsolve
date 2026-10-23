import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

p = Path('/tmp/os2026-p35')
repo = Path('/tmp/os2026-p10-repair.9doyhO')

def digest(f):
    h = hashlib.sha256()
    with f.open('rb') as src:
        for block in iter(lambda: src.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

subprocess.run(['python', '-I', str(p/'audit.py')], check=True, stdout=(p/'audit.log').open('w'))
meta = json.loads((p/'collected.json').read_text())
inputs = {}
roots = [p/'large-data', Path('/tmp/os2026-p33/accepted-data')]
roots += [Path('/tmp/os2026-p34')/(group+'-data') for group in ['holdout', 'fresh', 'validation']]
for root in roots:
    for f in sorted(root.rglob('*')):
        if f.is_file():
            inputs[str(f)] = dict(size=f.stat().st_size, sha256=digest(f))
runs = [json.loads(line) for line in (p/'runs.jsonl').read_text().splitlines()]
for name in sorted({r['case'] for r in runs}):
    for directory in ['cases', 'refs']:
        for f in (Path('~/os2026/data')/directory/name).rglob('*'):
            if f.is_file():
                inputs[str(f)] = dict(size=f.stat().st_size, sha256=digest(f))
(p/'input-hashes.json').write_text(json.dumps(inputs, indent=2)+'\n')
meta['input_hashes'] = inputs
(p/'collected.json').write_text(json.dumps(meta, indent=2)+'\n')

snapshot = p/'tool-snapshot'
for directory in ['tools/bench', 'tools/eval', 'tools/gen', 'tools/run']:
    for src in (repo/directory).rglob('*.py'):
        dst = snapshot/src.relative_to(repo)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
for rel in ['tools/case.py', 'env/run.sh', 'env/hosts/gpu02.sh', 'src/driver/definite.cpp',
            'src/driver/certificate.cpp', 'src/driver/certificate.hpp', 'include/hsolve/dense.hpp',
            'tests/CMakeLists.txt', 'tests/cmake/mpi_cli_failure.cmake']:
    src = repo/rel
    if src.exists():
        dst = snapshot/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
(p/'hardware.txt').write_text(subprocess.run(['lscpu'], capture_output=True, text=True, check=True).stdout)
(p/'ARCHIVE_README.txt').write_text(
    'P35 private workspace reuse and bounded nearest-rerun experiments. Production P29 unchanged.\n'
    'All builds, tests, generated numeric inputs, and solves ran on gpu02 CPU.\n'
    'Correctness runs used CPU8-15/12GiB. Timing qualification requires CPU16-31/32GiB exclusive guard plus external activity monitor.\n'
    'All completed solves, including failures/timeouts, are in runs.jsonl and raw/. Original tolerance, k, and independent evaluation remain in use.\n'
    'Full C++ regression uses the registered CMake OMP2/OpenBLAS1 settings and hides GPU devices. MPI and special thread cases are retained.\n'
    'Explicit memory budgets guide solver planning; measured peak may exceed them and is reported separately.\n'
    'New large inputs and their full prescribed spectra are included. Prior pressure inputs have hashes and are in the P34 archive.\n'
    'Scripts contain fixed paths, require the existing P29 checkout/dependencies and P28 complex SLEPc environment, and must use new output paths/tags when rerun.\n'
    'The comparison tool removes eigenvectors after independent evaluation.\n')
files = {}
for f in sorted(p.rglob('*')):
    if f.is_file():
        files['experiment/'+str(f.relative_to(p))] = f
for tag in meta['groups']:
    root = repo/'results/raw'/tag
    for f in sorted(root.rglob('*')):
        if f.is_file():
            files['raw/'+tag+'/'+str(f.relative_to(root))] = f
for root, names in [
    (Path('/tmp/os2026-p33'), ['libhsolve-requested.a', 'requested-build-hashes.json', 'band_backend.hpp', 'band_ldlh.cpp', 'steps.cpp', 'solver.cpp']),
    (Path('/tmp/os2026-p34'), ['definite_accepted.cpp', 'slepc-profiles.json'])]:
    for name in names:
        f = root/name
        if f.exists():
            files['dependencies/'+root.name+'/'+name] = f
manifest = {name: dict(size=f.stat().st_size, sha256=digest(f)) for name, f in files.items()}
mf = Path('/tmp/os2026-p35-manifest.json')
mf.write_text(json.dumps(manifest, indent=2)+'\n')
archive = Path('/tmp/os2026-p35-results.tar')
with tarfile.open(archive, 'w') as out:
    for name, f in files.items():
        out.add(f, arcname=name, recursive=False)
    out.add(mf, arcname='MANIFEST.json', recursive=False)
result = dict(path=str(archive), size=archive.stat().st_size, members=len(files)+1,
              content_members=len(files), sha256=digest(archive))
Path('/tmp/os2026-p35-archive.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
