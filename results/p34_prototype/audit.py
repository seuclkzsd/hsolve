import collections,hashlib,json
from pathlib import Path
p=Path('/tmp/os2026-p34');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def read(f):return json.loads(f.read_text())
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
runs=[json.loads(line) for line in (p/'runs.jsonl').read_text().splitlines()]
groups={}
for row in runs:
 tag=Path(row['out']).relative_to(repo/'results/raw').parts[0]
 group=groups.setdefault(tag,{}).setdefault(row['solver'],dict(attempts=0,valid=0,failures=[]))
 group['attempts']+=1
 if row['valid']:
  assert row['completeness'] in ['complete','consistent'],row
  group['valid']+=1
 else:group['failures'].append(dict(case=row['case'],out=row['out'],why=row.get('why'),pairs=row.get('pairs'),max_eta=row.get('max_eta')))
 assert row['ended_monotonic']>=row['started_monotonic']
assert len({r['out'] for r in runs})==len(runs),'Overwritten run directory'
def failures(data):
 return [dict(suite=s['name'],name=t['name'],failures=t['failures']) for s in data.get('testsuites',[]) for t in s['testsuite'] if t.get('failures')]
baseline=read(p/'certfast-baseline.json');baseline_failures=failures(baseline)
regressions={}
for variant in ['projected','carried','carriednative','bounded','boundednative','accepted','acceptednative']:
 root=p/('regression-'+variant)
 if not (root/'results.json').exists():continue
 rows=read(root/'results.json')
 all_failures=[dict(target=r['target'],**f) for r in rows for f in failures(read(root/(r['target']+'.json')))]
 baseline_only=[{k:v for k,v in f.items() if k!='target'} for f in all_failures]==baseline_failures
 regressions[variant]=dict(targets=len(rows),tests=sum(r['tests'] for r in rows),failures=sum(r['failures'] for r in rows),baseline_failure_only=baseline_only,details=all_failures)
production={str(repo/'build/release'/n):digest(repo/'build/release'/n) for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']}
assert production==read(p/'build-hashes.json')['production_before']
references=[]
for row in runs:
 if row['solver']!='slepc':continue
 f=Path(row['out'])/'report.json'
 if f.exists():
  r=read(f);references.append(dict(out=row['out'],scalar=r.get('petsc_scalar_type'),pc=r.get('factor_pc_type')))
assert all(x['scalar']=='complex128' and x['pc']=='lu' for x in references)
monitor=read(p/'screen-monitor-result.json') if (p/'screen-monitor-result.json').exists() else None
qualified_cases={}
if monitor and monitor.get('rows'):
 for name in sorted({r['case'] for r in monitor['rows']}):
  rows=[r for r in monitor['rows'] if r['case']==name]
  qualified_cases[name]=len(rows)==20 and all(r['performance_usable'] for r in rows)
work_examples=[]
for row in runs:
 if row['case']!='fresh-13-coupled-complex-hep' or not row['solver'].startswith('hsolve'):continue
 root=Path(row['out']);events=root.parent/('events-'+root.name+'.jsonl')
 records=[json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
 work_examples.append(dict(solver=row['solver'],out=row['out'],valid=row['valid'],max_eta=row.get('max_eta'),
  phases=row.get('phases'),events=[r for r in records if r.get('event') in ['lanczos','certificate','certificate_window_tightened','corrected_deflation','done']]))
metadata=dict(round='P34',host='gpu02',goal_achieved=False,production_adopted=False,production_hashes=production,
 full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),
 valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),groups=groups,regressions=regressions,
 baseline_regression=dict(tests=baseline['tests'],failures=baseline['failures'],details=baseline_failures),
 certificate_passed_but_invalid=[dict(case=r['case'],solver=r['solver'],out=r['out']) for r in runs if r.get('certificate',{}).get('passed') and not r['valid']],
 references=references,monitor=monitor,qualified_cases=qualified_cases,work_examples=work_examples,
 summaries={tag:read(p/(tag+'.json')) for tag in groups if (p/(tag+'.json')).exists()},
 caveats=['Shared-core correctness diagnostics are not performance comparisons.',
 'The shifted variant is rejected because it introduced a failure and excessive factorizations.',
 'Carrying corrected vectors changes the nearest deflated rerun; the separate window rerun path is unchanged.',
 'The carried prototype adds temporary block storage and has not passed production-scale memory-budget qualification.',
 'Strict monotone acceptance applies to each residual correction before the final block Rayleigh-Ritz; the final solve is independently checked.',
 'Untuned SLEPc failures on fresh pressure cases do not establish that tuned SLEPc cannot solve them.',
 'The two photonic cases use existing incomplete solver references, so external evaluation establishes consistency rather than a fully independent completeness proof.'])
(p/'collected.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({k:v for k,v in metadata.items() if k in ['full_solve_attempts','full_solve_valid','groups','regressions','baseline_regression','monitor']},indent=2))
