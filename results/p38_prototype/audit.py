import collections,hashlib,json,re,statistics
from pathlib import Path
p=Path('/tmp/os2026-p38');repo=Path('/tmp/os2026-p10-repair.9doyhO')
def read(f):return json.loads(f.read_text())
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def tag(row):return Path(row['out']).relative_to(repo/'results/raw').parts[0]
runs=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines()]
assert len({r['out'] for r in runs})==len(runs)
groups={};sources={};work=[]
for r in runs:
 g=groups.setdefault(tag(r),{}).setdefault(r['solver'],dict(attempts=0,valid=0,failures=[]));g['attempts']+=1
 if r['valid']:g['valid']+=1
 else:g['failures'].append({k:r.get(k) for k in ['case','out','why','error','max_eta','pairs']})
 if r['solver'].startswith('hsolve'):
  sources.setdefault(r['solver'],collections.Counter())[r.get('candidate_source','unknown')]+=1
  root=Path(r['out']);log=root.parent/('guard-'+root.name+'.stderr.txt')
  pattern=r'P38 adaptive_sector mode=(\d+) period=(\d+) n=(\d+) requested=(\d+) pairs=(\d+) success=(\d+) factors=(\d+) rhs=(\d+) seconds=([0-9.e+-]+)'
  sectors=[]
  for x in re.findall(pattern,log.read_text() if log.exists() else ''):
   item=dict(zip(['mode','period','n','requested','pairs','success','factors','rhs'],map(int,x[:8])));item['seconds']=float(x[8]);sectors.append(item)
  if sectors:work.append(dict(case=r['case'],out=r['out'],solver=r['solver'],inner_calls=len(sectors),inner_factorizations=sum(x['factors'] for x in sectors),inner_rhs=sum(x['rhs'] for x in sectors),requested_pair_sum=sum(x['requested'] for x in sectors),sectors=sectors))
expected={r['case']:r['expected_candidate'] for r in read(p/'case-manifest.json')};small=[]
for r in runs:
 if r['case'] not in expected or r['solver'] not in ['hsolve-partial','hsolve-adaptive']:continue
 assert r['valid'] and r['completeness']=='complete'
 assert r['candidate_source']==expected[r['case']],r
 if r['case']!='certificate-off':assert r['certificate']['passed'] and r['certificate']['method']=='exact'
 small.append(dict(case=r['case'],solver=r['solver'],candidate_source=r['candidate_source'],max_eta=r['max_eta'],certificate=r['certificate']))
assert len(small)==22
assert read(p/'diagnostic-qualified.json')['qualified']
contracts=read(p/'contract-check-results.json');assert len(contracts)==9
full=p/'full-adaptive';regrows=read(full/'results.json');counts=collections.Counter();failures=[];skips=[]
assert read(full/'summary.json')['success'] and len(regrows)==71
for row in regrows:
 f=full/(row['target']+'.json')
 if not f.exists():assert row['target']=='mpi-cli-helper-log';continue
 for suite in read(f)['testsuites']:
  for case in suite['testsuite']:
   identity=row['target']+':'+suite['name']+'.'+case['name'];counts['listed']+=1
   if case.get('failures'):counts['failed']+=1;failures.append(dict(test=identity,failures=case['failures']))
   elif case.get('result')=='SKIPPED':counts['skipped']+=1;skips.append(dict(test=identity,reasons=case.get('skipped')))
   elif case.get('status')=='NOTRUN' or case.get('result')=='SUPPRESSED':counts['disabled']+=1
   elif case.get('status')=='RUN' and case.get('result')=='COMPLETED':counts['passed']+=1
   else:raise AssertionError(case)
assert not failures and all(r['returncode']==0 for r in regrows)
production={str(repo/'build/release'/n):digest(repo/'build/release'/n) for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']}
expected_production={'hsolve':'045409af0138ab363106ab5d7483260b69a260ed2212bbbbbc29becb70bfc377','hsolve-mpi':'d46e2a435891f138f64acb679cda509285a6cc308756f2158fe461b4af2b6648','libhsolve.a':'9b5e0b567830e5f22f5c01796f1084f7ea49f5860be2aa89ac3bd8312b522fd1','libhsolve_blashook.so':'150ae2ed9beb3a06f26ee6b6670877e3048d2513d09441b122257a70fff09056'}
assert {Path(k).name:v for k,v in production.items()}==expected_production
source=digest(repo/'src/driver/definite.cpp');assert source=='f40ca695157d9334626b7928837716305c30439d257e0636ce9681e838d122d4'
builds={}
for v in ['control','partial','adaptive']:
 b=read(p/f'{v}-build-hashes.json');assert production==b['production_before']==b['production_after']
 for category in ['sources','experimental']:
  for name,sha in b[category].items():assert digest(p/name)==sha,(v,name)
 assert digest(Path(b['input_library']['path']))==b['input_library']['sha256'];builds[v]=b
monitor=read(p/'screen-monitor-result.json');qualified={};performance={};references=[]
if monitor.get('rows'):
 by_out={r['out']:r for r in monitor['rows']}
 for case in sorted({r['case'] for r in monitor['rows']}):
  rows=[r for r in runs if tag(r)=='p38-screen' and r['case']==case];c=collections.Counter(r['solver'] for r in rows)
  ok=len(c)==8 and all(n==5 for n in c.values()) and all(by_out[r['out']]['performance_usable'] for r in rows);qualified[case]=ok
  if not ok:continue
  stats={}
  for solver in c:
   selected=[r for r in rows if r['solver']==solver];values=[r['solver_s'] for r in selected]
   stats[solver]=dict(median_s=statistics.median(values),min_s=min(values),max_s=max(values),valid=len(selected),max_eta=max(r['max_eta'] for r in selected))
  for solver in stats:stats[solver]['time_over_slepc']=stats[solver]['median_s']/stats['slepc']['median_s']
  performance[case]=stats
for row in runs:
 if row['solver']=='slepc':
  r=read(Path(row['out'])/'report.json');assert r.get('petsc_scalar_type')=='complex128' and r.get('factor_pc_type')=='lu'
  references.append(dict(out=row['out'],config=row['config'],scope=row['config_scope'],source=row['config_source']))
result=dict(round='P38',host='gpu02',goal_achieved=False,production_adopted=False,full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),groups=groups,source_counts=sources,structure=read(p/'structure-results.json'),small_cases=small,contracts=contracts,modal_work=work,regression=dict(summary=read(full/'summary.json'),totals=dict(counts),failures=failures,skips=skips),production_hashes=production,production_source_sha256=source,builds=builds,monitor=monitor,qualified_cases=qualified,performance=performance,references=references,guards={f.name:read(f) for f in p.glob('*-guard.json')},caveats=['Shared-core diagnostic times are not performance evidence.','Only candidate construction changes; final original-pencil residual/rank checks and exact inertia certification remain mandatory.','Sector values decide where to request candidates, not certified spectral exclusion. Missing pairs use the original driver recovery.','Outer factor statistics exclude inner sector solves; their costs remain in parent time_total_s/time_iterate_s and detailed stderr records.','The two physical photonic inputs have incomplete external references.','No sparse matrix is densified by the solver. Dense full-spectrum reference is used only for new test matrices of order <=420.','Frozen private native libraries require previous P33-P37 dependencies; production P29 remains unchanged.'])
(p/'collected.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['full_solve_attempts','full_solve_valid','valid_completeness','qualified_cases']}));print(json.dumps(dict(regression=dict(counts),source_counts=sources)))
