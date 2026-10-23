import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

p = Path('/tmp/os2026-p36')
repo = Path('/tmp/os2026-p10-repair.9doyhO')

def digest(f):
    h = hashlib.sha256()
    with f.open('rb') as src:
        for block in iter(lambda: src.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

assert (p/'screen-monitor-result.json').exists(), 'Wait for timing monitor to terminate'
assert json.loads((p/'reuse-validation-guard.json').read_text())['returncode'] == 0
assert all(json.loads((p/('full-'+v)/'summary.json').read_text())['success'] for v in ['fused','simd','reuse'])
subprocess.run(['python', '-I', str(p/'audit.py')], check=True, stdout=(p/'audit.log').open('w'))
meta = json.loads((p/'collected.json').read_text())
inputs = {}
roots = [Path('/tmp/os2026-p35/large-data'), Path('/tmp/os2026-p33/accepted-data'), Path('/tmp/os2026-p33/contract-data-v2')]
roots += [Path('/tmp/os2026-p34')/(group+'-data') for group in ['holdout','fresh','validation']]
for root in roots:
    for f in sorted(root.rglob('*')):
        if f.is_file():
            inputs[str(f)] = dict(size=f.stat().st_size, sha256=digest(f))
for item in json.loads((p/'reuse-manifest.json').read_text()):
    for key in ['a','b','rhs']:
        if key in item:
            f = Path(item[key])
            inputs[str(f)] = dict(size=f.stat().st_size, sha256=digest(f))
runs = [json.loads(line) for line in (p/'runs.jsonl').read_text().splitlines()]
for name in sorted({r['case'] for r in runs}):
    for directory in ['cases','refs']:
        for f in (Path('~/os2026/data')/directory/name).rglob('*'):
            if f.is_file():
                inputs[str(f)] = dict(size=f.stat().st_size, sha256=digest(f))
(p/'input-hashes.json').write_text(json.dumps(inputs, indent=2)+'\n')
meta['input_hashes'] = inputs
(p/'collected.json').write_text(json.dumps(meta, indent=2)+'\n')

snapshot = p/'tool-snapshot'
for directory in ['tools/bench','tools/eval','tools/gen','tools/run']:
    for src in (repo/directory).rglob('*.py'):
        dst = snapshot/src.relative_to(repo)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
for rel in ['tools/case.py','env/run.sh','env/hosts/gpu02.sh','src/driver/definite.cpp',
            'src/driver/certificate.cpp','src/driver/certificate.hpp','include/hsolve/dense.hpp',
            'tests/CMakeLists.txt','tests/cmake/mpi_cli_failure.cmake']:
    src = repo/rel
    if src.exists():
        dst = snapshot/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
(p/'hardware.txt').write_text(subprocess.run(['lscpu'], capture_output=True, text=True, check=True).stdout)
(p/'ARCHIVE_README.txt').write_text(
    'P36 private fused RHS packing, SIMD Schur updates and checked factor reuse experiments. Production P29 unchanged.\n'
    'All builds, numerical verification and solves ran on gpu02 CPU.\n'
    'Correctness: CPU8-15/12GiB. Timing: CPU16-31/32GiB exclusive guard plus retained external-activity samples.\n'
    'All attempts are retained in runs.jsonl and raw/, with original tolerance, k and independent evaluation.\n'
    'The initial continuation exit75 intentionally deferred timing until the factor-reuse candidate passed; it was not a numerical failure.\n'
    'Full C++ regression uses OMP2/OpenBLAS1 with GPUs hidden; special affinity/thread cases and four MPI layouts are included.\n'
    'Native variants have narrow-band complex dispatch; all other inputs retain existing paths. SIMD may change rounding.\n'
    'The reuse variant keeps rejected factors unavailable to ordinary solve and activates them only for the matching-shift checked probe.\n'
    'Input hashes cover reused P33/P34/P35 corpora and standard cases. Those inputs are in their previous archives or shared data tree.\n'
    'Scripts use fixed paths and require the existing P29 checkout/dependencies and P28 complex SLEPc environment; reruns need new output tags.\n'
    'The comparison tool removes eigenvectors after independent evaluation. Binaries use -march=native and are private gpu02 prototypes.\n')
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
    (Path('/tmp/os2026-p33'), ['requested-manifest.json','requested-build-hashes.json','band_backend.hpp','band_ldlh.cpp','steps.cpp','solver.cpp']),
    (Path('/tmp/os2026-p34'), ['slepc-profiles.json']),
    (Path('/tmp/os2026-p35'), ['libhsolve-cappednative.a','hsolve-cappednative','definite_capped.cpp','capped-build-hashes.json'])]:
    for name in names:
        f = root/name
        assert f.exists(), f
        files['dependencies/'+root.name+'/'+name] = f
manifest = {name: dict(size=f.stat().st_size, sha256=digest(f)) for name,f in files.items()}
mf = Path('/tmp/os2026-p36-manifest.json')
mf.write_text(json.dumps(manifest, indent=2)+'\n')
archive = Path('/tmp/os2026-p36-results.tar')
with tarfile.open(archive, 'w') as out:
    for name,f in files.items():
        out.add(f, arcname=name, recursive=False)
    out.add(mf, arcname='MANIFEST.json', recursive=False)
result = dict(path=str(archive), size=archive.stat().st_size, members=len(files)+1,
              content_members=len(files), sha256=digest(archive))
Path('/tmp/os2026-p36-archive.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
