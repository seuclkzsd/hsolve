import collections,hashlib,json,statistics
from pathlib import Path
p=Path('/tmp/os2026-p37');repo=Path('/tmp/os2026-p10-repair.9doyhO')
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
for variant in ['control','scalar','dd']:
 rows=read(p/f'{variant}-check-results.json');manifest=read(p/f'{variant}-manifest.json')
 checks=[json.loads(s) for s in (p/f'{variant}-check.stdout').read_text().splitlines()]
 linear[variant]=dict(checks=len(rows),valid=sum(r['valid'] for r in rows),max_eta=max(r['eta'] for r in rows),
  singular_rejections=sum(bool(r.get('singular')) and not r['initial_valid'] for r in checks),
  fallback_inputs=sum(r.get('analyses',0)>1 for r in checks),inputs=len(manifest),failed_inputs=[r for r in checks if r.get('valid') is False])
 assert len(rows)==1540 and all(r['valid'] for r in rows)
residual_initial=read(p/'residual-check-results.json');decimal_initial=read(p/'decimal-check-results.json')
residual=read(p/'residual-check-results-v2.json');decimal=read(p/'decimal-check-results-v2.json')
assert len(residual)==1540 and all(r['valid'] for r in residual)
assert len(decimal)==648 and all(r['valid'] for r in decimal)
boundary=read(p/'boundary-results-v2.json') if (p/'boundary-results-v2.json').exists() else []
boundary_initial=read(p/'boundary-results.json') if (p/'boundary-results.json').exists() else []
boundary_decimal=read(p/'boundary-decimal-results.json') if (p/'boundary-decimal-results.json').exists() else []
if boundary_decimal:assert len(boundary_decimal)==1296 and all(r['valid'] for r in boundary_decimal)
if boundary:assert len(boundary)==320 and all(r['valid'] for r in boundary)
if boundary:
 for name,sha in read(p/'boundary-build-hashes.json').items():assert digest(p/name)==sha
residual_summary=dict(checks=len(residual),valid=sum(r['valid'] for r in residual),vectorized=sum(r['vectorized'] for r in residual),max_ratio=max(r['residual_difference_ratio'] for r in residual),decimal_checks=len(decimal),decimal_valid=sum(r['valid'] for r in decimal),
 initial_raw_matrix_reference=dict(checks=len(residual_initial),failed=sum(not r['valid'] for r in residual_initial),decimal_checks=len(decimal_initial),decimal_failed=sum(not r['valid'] for r in decimal_initial),reason='Initial kernel-only reference used raw files; load_matrix first applies its existing Hermitian normalization. Version2 reconstructs that input. Original-file full linear checks were unchanged and passed.'))
regressions={}
for variant in ['scalar','dd']:
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
for variant in ['control','scalar','dd']:
 b=read(p/f'{variant}-build-hashes.json');assert production==b['production_before']==b['production_after']
 for name,sha in b['experimental'].items():assert digest(p/name)==sha
 for name,sha in b['sources'].items():assert digest(p/name)==sha
 assert digest(Path(b['input_library']['path']))==b['input_library']['sha256']=='7aa757a9dce860103d3cb5113e44c08b3fd43d9902665945035e7f1ed4959a3a';builds[variant]=b
monitor=read(p/'screen-monitor-result.json') if (p/'screen-monitor-result.json').exists() else None
qualified={};performance={}
if monitor and monitor.get('rows'):
 by_out={r['out']:r for r in monitor['rows']}
 for case in sorted({r['case'] for r in monitor['rows']}):
  rows=[r for r in runs if tag(r)=='p37-screen' and r['case']==case];counts=collections.Counter(r['solver'] for r in rows)
  ok=len(counts)==6 and all(n==5 for n in counts.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
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
 if row['solver'] in ['hsolve-control','hsolve-scalar','hsolve-dd']:
  f=root.parent/('events-'+root.name+'.jsonl')
  if f.exists():
   events=[json.loads(s) for s in f.read_text().splitlines()]
   paths.append(dict(case=row['case'],solver=row['solver'],out=row['out'],events=[e for e in events if e.get('event') in ['factor_backend','private_backend_fallback','checked_requested_shift']]))
assert all(r['scalar']=='complex128' and r['pc']=='lu' for r in references)
contracts=read(p/'contract-check-results.json') if (p/'contract-check-results.json').exists() else None
reference_window=read(p/'reference-window-results-v2.json')
assert read(p/'reference-v2-guard.json')['returncode']==0
assert all(r['window_supported'] for r in reference_window['cases'])
for name,sha in reference_window['hashes'].items():assert digest(p/name)==sha
reference_window['initial_failure']='Initial reference-count helper incorrectly required real-valued pencils and aborted on the actual complex input. Version2 preserves complex sparse values and promotes real B when needed; failed logs and original sources are retained.'
result=dict(round='P37',host='gpu02',goal_achieved=False,production_adopted=False,full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),
 valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),groups=groups,linear_checks=linear,
 residual_summary=residual_summary,residual_checks=residual,decimal_checks=decimal,boundary_checks=boundary,boundary_decimal_checks=boundary_decimal,boundary_initial=dict(checks=len(boundary_initial),failed=sum(not r["valid"] for r in boundary_initial),reason="The first arbitrary-vector boundary comparator did not account for final complex<double> rounding. Version2 separates half-ULP output rounding and long-double reference error, and adds 90-digit independent checks; solver source and acceptance thresholds unchanged."),contracts=contracts,regressions=regressions,
 production_hashes=production,production_source_sha256=production_source,builds=builds,monitor=monitor,qualified_cases=qualified,performance=performance,references=references,reference_window=reference_window,backend_paths=paths,
 guards={name:read(p/name) for name in ['build-checks-guard.json','diagnostic-guard.json','full-guard.json','residual-v2-guard.json','boundary-guard.json','boundary-v2-guard.json','screen-guard.json','reference-guard.json','reference-v2-guard.json'] if (p/name).exists()},
 caveats=['Shared-core diagnostic timings are not performance evidence.',
  'Frozen P36 reuse is the native control; a separate recompilation control distinguishes layout effects.',
  'The scalar candidate changes long-double loop layout while preserving original-pencil arithmetic and thresholds.',
  'The dd candidate uses compensated AVX512 arithmetic only for the first refinement correction; original long-double acceptance and requested-shift probes remain mandatory.',
  'The first extra kernel-only verifier used raw input files rather than the actual Hermitian-normalized kernel input; failed records are retained. No solver source or thresholds changed for version2.',
  'Ordinary original-file linear solve checks are independent of the kernel-only normalized-input reference.',
  'Extreme coefficients/vectors and nonfinite data use the original long-double residual path.',
  'Actual P36 logs show ordinary narrowband certificates already use native main-factor counts; the initial proposed independent MUMPS counter optimization was not implemented.',
  'Native dispatch scope is unchanged; physical photonic cases retain their prior path. The rods and spheres inputs use complex Hermitian matrices.',
  'Photonic external references are incomplete; consistent does not establish independent completeness.',
  'Private -march=native prototypes are specific to gpu02 and not portable production binaries.',
  'Specified SLEPc configurations do not cover every open-source method.' ])
(p/'collected.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['full_solve_attempts','full_solve_valid','linear_checks','residual_summary','qualified_cases']},indent=2))
