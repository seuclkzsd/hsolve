import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
p=Path('/tmp/os2026-p40');v=p/'v3';repo=Path('/tmp/os2026-p10-repair.9doyhO')
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
assert (p/'screen-monitor-result.json').exists()
series=json.loads((v/'candidate-series.json').read_text())
for batch in series['batches']:assert Path(batch['monitor']).exists()
for name in ['diagnostic-guard.json','full-guard.json','boundary-v3-guard.json']:assert json.loads((v/name).read_text())['returncode']==0
subprocess.run(['python','-I',str(p/'audit.py')],check=True,stdout=(p/'audit.log').open('w'))
meta=json.loads((p/'collected.json').read_text());inputs={}
roots=[Path('/tmp/os2026-p39/data'),Path('/tmp/os2026-p38/data'),Path('/tmp/os2026-p35/large-data'),Path('/tmp/os2026-p33/accepted-data'),Path('/tmp/os2026-p33/contract-data-v2')]
roots += [Path('/tmp/os2026-p34')/(group+'-data') for group in ['holdout','fresh','validation']]
for root in roots:
 for f in sorted(root.rglob('*')):
  if f.is_file():inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
for manifest in [p/'enclosed-manifest.json',Path('/tmp/os2026-p37/boundary-manifest.json')]:
 for row in json.loads(manifest.read_text()):
  for key in ['a','b','rhs']:
   if key in row:
    f=Path(row[key]);inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
runs=[json.loads(line) for f in [p/'runs.jsonl',v/'candidate-runs.jsonl'] for line in f.read_text().splitlines()]
for name in sorted({r['case'] for r in runs}):
 for directory in ['cases','refs']:
  for f in (Path('/share/home/linzihan/os2026/data')/directory/name).rglob('*'):
   if f.is_file():inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
(p/'input-hashes.json').write_text(json.dumps(inputs,indent=2)+'\n');meta['input_hashes']=inputs
(p/'collected.json').write_text(json.dumps(meta,indent=2)+'\n')
snapshot=p/'tool-snapshot'
for directory in ['tools/bench','tools/eval','tools/gen','tools/run']:
 for src in (repo/directory).rglob('*.py'):
  dst=snapshot/src.relative_to(repo);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
for rel in ['tools/case.py','env/run.sh','env/hosts/gpu02.sh','src/driver/definite.cpp','src/driver/certificate.cpp','src/driver/certificate.hpp','include/hsolve/dense.hpp','src/driver/helpers.cpp','src/driver/helpers.hpp','src/driver/internal.hpp','src/eigen/block_lanczos.cpp','src/eigen/block_lanczos.hpp','src/factor/mumps_factorization.cpp','tests/CMakeLists.txt','tests/cmake/mpi_cli_failure.cmake']:
 src=repo/rel
 if src.exists():
  dst=snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
(p/'hardware.txt').write_text(subprocess.run(['lscpu'],capture_output=True,text=True,check=True).stdout)
(p/'ARCHIVE_README.txt').write_text('''P40: thread-count sweep and original-pencil SIMD residual enclosure.
All builds and numerical tests ran on gpu02 CPU. Production P29 unchanged.
Final kernel is v3, combining P37 DD correction and P39 per-sector factor reuse.
Enclosure <= original 1e-12 permits early internal acceptance; otherwise original long-double path remains.
Original eigenpair residual/rank verification and exact inertia certificates remain mandatory.
v1 had numeric success but implicit FMA contraction mismatched proof. v2 disables contraction; v3 also checks worker MXCSR.
v3 boundary harness first missed omp.h; next expected persistent worker rounding, disproved by probe. Final harness verifies runtime reset. All failed versions/logs retained.
Main diagnostics: 194 solves, 34 small dense-oracle checks, 18 contracts, 2 large sparse tests per variant.
Each final variant has 71 regression invocations including four MPI layouts.
Thread sweep: 11 variants, 9 cases, 3 repetitions. Only full qualified case groups may inform exploratory conclusions.
Final timing: 6 solvers, 9 cases, 5 repetitions, predefined up to 4 batches; select first qualified full case group.
Timing is CPU16-31/32GiB exclusive guard with target/sibling/global external-activity monitoring; all samples retained.
Raw logs and entire numerical outputs are included. Earlier large input data are content-hashed; small P38/P39 data are included.
Fixed paths require frozen P29 checkout, P33-P39 dependencies and P28 complex128 SLEPc. Use new tags/directories for reruns.
''')
files={}
for f in sorted(p.rglob('*')):
 if f.is_file():files['experiment/'+str(f.relative_to(p))]=f
for tag in meta['groups']:
 root=repo/'results/raw'/tag
 for f in sorted(root.rglob('*')):
  if f.is_file():files['raw/'+tag+'/'+str(f.relative_to(root))]=f
for root,names in [
 (Path('/tmp/os2026-p33'),['requested-manifest.json','requested-build-hashes.json','band_backend.hpp','band_ldlh.cpp','steps.cpp','solver.cpp']),
 (Path('/tmp/os2026-p34'),['slepc-profiles.json']),
 (Path('/tmp/os2026-p35'),['definite_capped.cpp','capped-build-hashes.json']),
 (Path('/tmp/os2026-p36'),['reuse-build-hashes.json','band_backend_reuse.hpp','band_ldlh.cpp','solver_reuse.cpp']),
 (Path('/tmp/os2026-p37'),['libhsolve-control.a','control-build-hashes.json','scalar-build-hashes.json','dd-build-hashes.json','band_backend.hpp','solver.cpp','band_ldlh.cpp','boundary-manifest.json']),
 (Path('/tmp/os2026-p38'),['adaptive_bloch.hpp','adaptive-build-hashes.json','definite_v2.cpp','case-manifest.json']),
 (Path('/tmp/os2026-p39'),['libhsolve-reuse.a','reuse-build-hashes.json','definite.cpp','cycle.hpp','cached_candidates.inc','case-manifest.json','extra-case-manifest-v2.json'])]:
 for name in names:
  f=root/name;assert f.exists(),f;files['dependencies/'+root.name+'/'+name]=f
for root in [Path('/tmp/os2026-p38/data'),Path('/tmp/os2026-p39/data')]:
 for f in sorted(root.rglob('*')):
  if f.is_file():files['dependencies/'+root.parent.name+'/data/'+str(f.relative_to(root))]=f
manifest={name:dict(size=f.stat().st_size,sha256=digest(f)) for name,f in files.items()}
mf=Path('/tmp/os2026-p40-manifest.json');mf.write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/tmp/os2026-p40-results.tar')
with tarfile.open(archive,'w') as out:
 for name,f in files.items():out.add(f,arcname=name,recursive=False)
 out.add(mf,arcname='MANIFEST.json',recursive=False)
result=dict(path=str(archive),size=archive.stat().st_size,members=len(files)+1,content_members=len(files),sha256=digest(archive))
Path('/tmp/os2026-p40-archive.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
