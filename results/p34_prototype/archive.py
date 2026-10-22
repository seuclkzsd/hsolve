import hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
p=Path('/tmp/os2026-p34');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
subprocess.run(['python',str(p/'audit.py')],check=True,stdout=(p/'audit.log').open('w'))
meta=json.loads((p/'collected.json').read_text());tags=sorted(meta['groups'])
inputs={};external={}
for root in [p/'holdout-data',p/'fresh-data',p/'validation-data',Path('/tmp/os2026-p33/accepted-data')]:
 for f in sorted(root.rglob('*')):
  if not f.is_file():continue
  inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
  if not f.is_relative_to(p):external['inputs/accepted-data/'+str(f.relative_to(root))]=f
main_cases=sorted({r['case'] for r in meta['summaries'].get('p34-carried-main',{}).get('rows',[])})
for name in main_cases:
 for directory in ['cases','refs']:
  for f in (Path('/share/home/linzihan/os2026/data')/directory/name).rglob('*'):
   if f.is_file():inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
(p/'input-hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
meta['input_hashes']=inputs
(p/'collected.json').write_text(json.dumps(meta,indent=2)+'\n')
snapshot=p/'tool-snapshot';snapshot.mkdir(exist_ok=True)
for directory in ['tools/bench','tools/eval','tools/gen','tools/run']:
 for src in (repo/directory).rglob('*.py'):
  dst=snapshot/src.relative_to(repo);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
for rel in ['tools/case.py','env/run.sh','env/hosts/gpu02.sh','src/driver/definite.cpp','src/driver/projection.cpp','src/driver/certificate.cpp','src/driver/certificate.hpp','tests/cpp/test_certfast.cpp']:
 src=repo/rel;dst=snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
for name in ['libhsolve-requested.a','libhsolve-requestedlu.a','band_backend.hpp','band_ldlh.cpp','steps.cpp','solver.cpp','build.py','requested-build-hashes.json']:
 src=Path('/tmp/os2026-p33')/name
 if src.exists():external['p33-dependencies/'+name]=src
(p/'hardware.txt').write_text(subprocess.run(['lscpu'],capture_output=True,text=True,check=True).stdout)
(p/'ARCHIVE_README.txt').write_text('P34 private residual correction, corrected deflation, and certificate-window experiments. Production P29 unchanged.\n'
 'All builds/tests/numerics ran on gpu02. Shared-core diagnostics (8-15,12GiB) are correctness evidence only. Formal timing, if present, requires the16-31 exclusive slot and monitor qualification.\n'
 'guarded: monotone correction acceptance; projected: also B-projection; shifted: per-pair Rayleigh shifts, rejected; carried: corrected selected vectors into deflation; refined: bounded additional correction passes; windowed: limit distant-hint expansion; bounded: refined+windowed. native suffix uses P33 requested-shift backend.\n'
 'Every completed solve attempt is in runs.jsonl, including failures. Guard and raw logs retain timeouts and incomplete processes. Completeness, original residual, and k all matter; certificate.passed alone is not sufficient.\n'
 'Regression failures are retained and compared with the unmodified baseline. No assertions or tolerances were weakened.\n'
 'Inputs for all new synthetic cases are included; standard benchmark input/reference files have hashes. The comparison tool removes eigenvectors after independent evaluation.\n'
 'Scripts have fixed paths and require the existing P29 checkout/dependencies and P28 native complex SLEPc environment. P33 native input libraries/sources are included. Use new output directories/tags on rerun.\n')
files=dict(external)
for f in sorted(p.rglob('*')):
 if f.is_file():files['experiment/'+str(f.relative_to(p))]=f
for tag in tags:
 root=repo/'results/raw'/tag
 for f in sorted(root.rglob('*')):
  if f.is_file():files['raw/'+tag+'/'+str(f.relative_to(root))]=f
manifest={name:dict(size=f.stat().st_size,sha256=digest(f)) for name,f in files.items()}
mf=Path('/tmp/os2026-p34-manifest.json');mf.write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/tmp/os2026-p34-results.tar')
with tarfile.open(archive,'w') as out:
 for name,f in files.items():out.add(f,arcname=name,recursive=False)
 out.add(mf,arcname='MANIFEST.json',recursive=False)
result=dict(path=str(archive),size=archive.stat().st_size,members=len(files)+1,content_members=len(files),sha256=digest(archive))
Path('/tmp/os2026-p34-archive.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
