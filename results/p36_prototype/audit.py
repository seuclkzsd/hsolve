import collections,hashlib,json,statistics
from pathlib import Path
p=Path('/tmp/os2026-p36');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def read(f):return json.loads(f.read_text())
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def tag(row):return Path(row['out']).relative_to(repo/'results/raw').parts[0]
runs=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines()]
assert len({r['out'] for r in runs})==len(runs),'Overwritten result directory'
groups={}
for r in runs:
 g=groups.setdefault(tag(r),{}).setdefault(r['solver'],dict(attempts=0,valid=0,failures=[]))
 g['attempts']+=1
 if r['valid']:
  assert r['completeness'] in ['complete','consistent'];g['valid']+=1
 else:g['failures'].append({k:r.get(k) for k in ['case','out','why','error','max_eta','pairs']})
 assert r['ended_monotonic']>=r['started_monotonic']
linear={}
for variant in ['control','fused','simd','reuse']:
 rows=read(p/f'{variant}-check-results.json');manifest=read(p/f'{variant}-manifest.json')
 checks=[json.loads(s) for s in (p/f'{variant}-check.stdout').read_text().splitlines()]
 linear[variant]=dict(checks=len(rows),valid=sum(r['valid'] for r in rows),max_eta=max(r['eta'] for r in rows),
  singular_rejections=sum(bool(r.get('singular')) and not r['initial_valid'] for r in checks),
  fallback_inputs=sum(r.get('analyses',0)>1 for r in checks),inputs=len(manifest),failed_inputs=[r for r in checks if r.get('valid') is False])
 assert len(rows)==1540 and all(r['valid'] for r in rows)
eq=read(p/'fused-equivalence.json');assert len(eq)==1540 and all(r['identical'] for r in eq)
regressions={}
for variant in ['fused','simd','reuse']:
 root=p/('full-'+variant)
 if not (root/'summary.json').exists():continue
 rows=read(root/'results.json');counts=collections.Counter();failures=[];skips=[]
 for row in rows:
  f=root/(row['target']+'.json')
  if not f.exists():assert row['target']=='mpi-cli-helper-log';continue
  for suite in read(f)['testsuites']:
   for case in suite['testsuite']:
    identity=row['target']+':'+suite['name']+'.'+case['name'];counts['listed']+=1
    if case.get('failures'):counts['failed']+=1;failures.append(dict(test=identity,failures=case['failures']))
    elif case.get('result')=='SKIPPED':counts['skipped']+=1;skips.append(dict(test=identity,reasons=case.get('skipped')))
    elif case.get('status')=='NOTRUN' or case.get('result')=='SUPPRESSED':counts['disabled']+=1
    elif case.get('status')=='RUN' and case.get('result')=='COMPLETED':counts['passed']+=1
    else:raise AssertionError(case)
 regressions[variant]=dict(summary=read(root/'summary.json'),invocations=len(rows),totals=dict(counts),failures=failures,skips=skips,
  nonzero_invocations=[r for r in rows if r['returncode']],environment=dict(OMP_NUM_THREADS=2,OPENBLAS_NUM_THREADS=1,CUDA_VISIBLE_DEVICES='',HSOLVE_TEST_GPU_DEVICE=''),
  caveat='Counts include separately invoked thread/affinity tests and each MPI rank layout, not unique test identities.')
production={str(repo/'build/release'/n):digest(repo/'build/release'/n) for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']}
expected_production={'hsolve':'045409af0138ab363106ab5d7483260b69a260ed2212bbbbbc29becb70bfc377',
 'hsolve-mpi':'d46e2a435891f138f64acb679cda509285a6cc308756f2158fe461b4af2b6648',
 'libhsolve.a':'9b5e0b567830e5f22f5c01796f1084f7ea49f5860be2aa89ac3bd8312b522fd1',
 'libhsolve_blashook.so':'150ae2ed9beb3a06f26ee6b6670877e3048d2513d09441b122257a70fff09056'}
assert {Path(k).name:v for k,v in production.items()}==expected_production
production_source=digest(repo/'src/driver/definite.cpp');assert production_source=='f40ca695157d9334626b7928837716305c30439d257e0636ce9681e838d122d4'
builds={}
for variant in ['control','fused','simd','reuse']:
 b=read(p/f'{variant}-build-hashes.json');assert production==b['production_before']==b['production_after']
 for name,sha in b['experimental'].items():assert digest(p/name)==sha
 for name,sha in b['sources'].items():assert digest(p/name)==sha
 assert digest(Path(b['input_library']['path']))==b['input_library']['sha256']=='ee219a931f61b796f0589416c52c2fdca97edbfc8b39291dc4d1757a6674f76e';builds[variant]=b
monitor=read(p/'screen-monitor-result.json') if (p/'screen-monitor-result.json').exists() else None
qualified={};performance={}
if monitor and monitor.get('rows'):
 by_out={r['out']:r for r in monitor['rows']}
 for case in sorted({r['case'] for r in monitor['rows']}):
  rows=[r for r in runs if tag(r)=='p36-screen' and r['case']==case];counts=collections.Counter(r['solver'] for r in rows)
  ok=len(counts)==7 and all(n==5 for n in counts.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
  qualified[case]=ok
  if not ok:continue
  stats={}
  for solver in counts:
   selected=[r for r in rows if r['solver']==solver];values=[r['solver_s'] for r in selected]
   stats[solver]=dict(median_s=statistics.median(values),min_s=min(values),max_s=max(values),wall_median_s=statistics.median(r['wall_s'] for r in selected),
    valid=len(selected),max_eta=max(r['max_eta'] for r in selected),peak_gib=max(max(r.get('peak_rss_gib') or 0,(r.get('solver_peak_bytes') or 0)/2**30) for r in selected),
    phase_medians={key:statistics.median(r['phases'][key] for r in selected) for key in selected[0].get('phases',{}) if all(r.get('phases',{}).get(key) is not None for r in selected)})
  for solver in stats:
   stats[solver]['time_over_slepc']=stats[solver]['median_s']/stats['slepc']['median_s']
   stats[solver]['time_over_native']=stats[solver]['median_s']/stats['hsolve-native']['median_s']
  performance[case]=stats
references=[];paths=[]
for row in runs:
 root=Path(row['out']);f=root/'report.json'
 if row['solver']=='slepc' and f.exists():
  r=read(f);references.append(dict(out=row['out'],scalar=r.get('petsc_scalar_type'),pc=r.get('factor_pc_type'),config=row.get('config'),scope=row.get('config_scope'),source=row.get('config_source')))
 if row['solver'] in ['hsolve-control','hsolve-fused','hsolve-simd','hsolve-reuse']:
  f=root.parent/('events-'+root.name+'.jsonl')
  if f.exists():
   events=[json.loads(s) for s in f.read_text().splitlines()]
   paths.append(dict(case=row['case'],solver=row['solver'],out=row['out'],events=[e for e in events if e.get('event') in ['factor_backend','private_backend_fallback','checked_requested_shift']]))
assert all(r['scalar']=='complex128' and r['pc']=='lu' for r in references)
contracts=read(p/'contract-check-results.json') if (p/'contract-check-results.json').exists() else None
reuse_contracts=read(p/'reuse-contract-check-results.json') if (p/'reuse-contract-check-results.json').exists() else None
reuse_probes=read(p/'reuse-probe-results.json') if (p/'reuse-probe-results.json').exists() else None
result=dict(round='P36',host='gpu02',goal_achieved=False,production_adopted=False,full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),
 valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),groups=groups,linear_checks=linear,
 fused_equivalence=dict(checks=len(eq),identical=sum(r['identical'] for r in eq)),contracts=contracts,reuse_contracts=reuse_contracts,reuse_probes=reuse_probes,regressions=regressions,
 production_hashes=production,production_source_sha256=production_source,builds=builds,monitor=monitor,qualified_cases=qualified,performance=performance,references=references,backend_paths=paths,
 guards={name:read(p/name) for name in ['build-checks-guard.json','diagnostic-guard.json','full-guard.json','reuse-validation-guard.json','screen-guard.json'] if (p/name).exists()},
 caveats=['Shared-core diagnostic timings are not performance evidence.',
  'P35 cappednative is the frozen native control. A separate recompilation control distinguishes code-layout effects from enabled optimizations.',
  'Packing equivalence checks compare complete linear outputs, while independent residual and inertia checks validate both candidates.',
  'The reuse variant keeps a factor rejected only by null detection unavailable to ordinary solve; only the checked matching-shift probe may activate it.',
  'The SIMD factor updates can change rounding and pivot trajectories; final original-problem residuals and exact counts remain required.',
  'Native dispatch scope is unchanged: graph-selected narrow-band complex exact solves; unsupported cases retain the original path.',
  'Photonic external references are incomplete; consistent does not establish independent completeness.',
  'Candidates are built for gpu02 with -march=native and are private prototypes, not portable production binaries.',
  'The benchmark tests specified SLEPc configurations, not every open-source method.'])
(p/'collected.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['full_solve_attempts','full_solve_valid','linear_checks','fused_equivalence','qualified_cases']},indent=2))
