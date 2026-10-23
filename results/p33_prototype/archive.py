import hashlib,json,subprocess,tarfile
from pathlib import Path
p=Path('/tmp/os2026-p33');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
runs=[json.loads(x) for x in (p/'runs.jsonl').read_text().splitlines()]
tags=sorted({Path(x['out']).relative_to(repo/'results/raw').parts[0] for x in runs})
summaries={tag:json.loads((p/(tag+'.json')).read_text()) for tag in tags}
assert len([r for r in runs if '/p33-diagnostic/' in r['out']])==18
assert len([r for r in runs if '/p33-diagnostic/' in r['out'] and not r['valid']])==2
known_failure_tags={'p33-diagnostic','p33-accepted-contracts','p33-stress-block16'}
assert all(r['valid'] and r['completeness']=='complete' for r in runs if Path(r['out']).relative_to(repo/'results/raw').parts[0] not in known_failure_tags)
monitor=json.loads((p/'screen-monitor-result.json').read_text()) if (p/'screen-monitor-result.json').exists() else {}
qualified={}
if 'p33-screen' in summaries:
 for row in summaries['p33-screen']['rows']:
  matching=[x for x in monitor.get('rows',[]) if x['case']==row['case']]
  qualified[row['case']]=len(matching)==30 and all(x['performance_usable'] for x in matching)
references=[]
for tag in tags:
 for f in (repo/'results/raw'/tag).glob('*/slepc*/report.json'):
  r=json.loads(f.read_text());references.append(dict(path=str(f),scalar=r.get('petsc_scalar_type'),pc=r.get('factor_pc_type')))
assert all(x['scalar']=='complex128' and x['pc']=='lu' for x in references)
prod={str(repo/'build/release'/n):digest(repo/'build/release'/n) for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']}
assert prod==json.loads((p/'requested-build-hashes.json').read_text())['production_before']
checks={v:json.loads((p/f'{v}-check-results.json').read_text()) for v in ['requested','requestedlu']}
assert sum(len(x) for x in checks.values())==3080 and all(x['valid'] for rows in checks.values() for x in rows)
inputs={};external={}
for item in json.loads((p/'requested-manifest.json').read_text()):
 for key in ['a','b','rhs']:
  if key in item:
   f=Path(item[key]);inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
   if not f.is_relative_to(p):external['inputs/'+str(f.relative_to('/tmp'))]=f
for name in [row['case'] for row in summaries['p33-diagnostic']['rows']]:
 for directory in ['cases','refs']:
  for f in (Path('~/os2026/data')/directory/name).rglob('*'):
   if f.is_file():inputs[str(f)]=dict(size=f.stat().st_size,sha256=digest(f))
(p/'input-hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
meta=dict(round='P33',host='gpu02',goal_achieved=False,production_adopted=False,production_hashes=prod,
 summaries=summaries,monitor=monitor,qualified_cases=qualified,linear_checks=checks,
 full_solve_attempts=len(runs),full_solve_valid=sum(bool(x['valid']) for x in runs),
 hsolve_certificate_reports=sum(x['solver'].startswith('hsolve') and x.get('certificate') is not None for x in runs),
 hsolve_valid_with_certificate=sum(bool(x.get('valid')) and bool(x.get('certificate',{}).get('passed')) for x in runs),
 hsolve_certificate_passed=sum(bool(x.get('certificate',{}).get('passed')) for x in runs),references=references,input_hashes=inputs,
 failures=[r for r in runs if not r['valid']],
 contracts=json.loads((p/'contract-check-results.json').read_text()),recovery=json.loads((p/'recovery-results.json').read_text()),
 correctness_gate=json.loads((p/'correctness-qualified.json').read_text()),
 caveats=['Initial diagonal exact-singular fixtures were automatically loaded as real and did not exercise the private backend; corrected complex fixtures and separate runs are included.',
 'Recovery-only binaries use the initial unsafe probe with the new driver recovery and are excluded from performance.',
 'Probe RHS threshold is a strategy screen, not a condition number or forward error bound.',
 'Private backend still lacks full production interface, memory budget and CPU dispatch qualification.'])
(p/'collected.json').write_text(json.dumps(meta,indent=2)+'\n')
(p/'hardware.txt').write_text(subprocess.run(['lscpu'],capture_output=True,text=True,check=True).stdout)
snapshot=p/'tool-snapshot';snapshot.mkdir(exist_ok=True)
for rel in ['tools/run/guard.py','tools/bench/compare.py','tools/bench/baseline_slepc.py','tools/gen/synthetic.py','tools/case.py','env/run.sh','env/hosts/gpu02.sh']:
 src=repo/rel
 if src.exists():
  dst=snapshot/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
(snapshot/'slepc-complex-profiles.json').write_bytes(Path('/tmp/os2026-p28/slepc-complex-profiles.json').read_bytes())
for name in ['hsolve-counts','hsolve-lucached']:
 src=Path('/tmp/os2026-p32')/name;dst=snapshot/name;dst.write_bytes(src.read_bytes())
(p/'ARCHIVE_README.txt').write_text('P33 private requested-shift experiments. Production P29 unchanged.\n'
 'Initial unsafe binaries/sources are in initial-failed. Main band_backend.hpp/solver.cpp are v2 with RHS-relative probe screen and whole-solve MUMPS recovery.\n'
 'recovery-only intentionally uses the initial unsafe probe with the v2 driver to verify actual exception and incomplete-result recovery. Never benchmark it as a candidate.\n'
 'All builds/numerics on gpu02. Correctness uses cores8-15/12GiB. Performance uses cores16-31/32GiB and exclusive guard. See all monitor records and qualified_cases.\n'
 'Two performance startups were rejected by guard before any benchmark. screen-start-rejected and screen-start-rejected-v2 retain evidence. The idle filter incorrectly treated root0 as all processes; fixed with regression check. Run-phase filters use actual guarded pid and were not affected. Corrected monitor requires60s real stable idle.\n'
 'Linear input/output and both original and corrected contract inputs are included. Main benchmark inputs have hashes; comparison removes eigenvectors after evaluation.\n'
 'Scripts use fixed paths and need the existing P29 checkout/dependencies and P28 complex SLEPc environment. Change paths/tags on reproduction.\n')
files=dict(external)
for f in sorted(p.rglob('*')):
 if f.is_file():files['experiment/'+str(f.relative_to(p))]=f
for tag in tags:
 root=repo/'results/raw'/tag
 for f in sorted(root.rglob('*')):
  if f.is_file():files['raw/'+tag+'/'+str(f.relative_to(root))]=f
manifest={name:dict(size=f.stat().st_size,sha256=digest(f)) for name,f in files.items()}
mf=Path('/tmp/os2026-p33-manifest.json');mf.write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/tmp/os2026-p33-results.tar')
with tarfile.open(archive,'w') as out:
 for name,f in files.items():out.add(f,arcname=name,recursive=False)
 out.add(mf,arcname='MANIFEST.json',recursive=False)
result=dict(path=str(archive),size=archive.stat().st_size,members=len(files)+1,content_members=len(files),sha256=digest(archive))
Path('/tmp/os2026-p33-archive.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
