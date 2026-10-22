import collections,hashlib,json,re,statistics
from pathlib import Path
p=Path('/tmp/os2026-p39');p38=Path('/tmp/os2026-p38');repo=Path('/tmp/os2026-p10-repair.9doyhO')
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
pattern=r'P39 sector mode=(\d+) period=(\d+) n=(\d+) requested=(\d+) pairs=(\d+) success=(\d+) reused=(\d+) analyses=(\d+) factors=(\d+) rhs=(\d+) shift=([0-9.e+-]+) seconds=([0-9.e+-]+)'
for r in runs:
 g=groups.setdefault(tag(r),{}).setdefault(r['solver'],dict(attempts=0,valid=0,failures=[]));g['attempts']+=1
 if r['valid']:g['valid']+=1
 else:g['failures'].append({k:r.get(k) for k in ['case','out','why','error','max_eta','pairs']})
 if r['solver'].startswith('hsolve'):
  sources.setdefault(r['solver'],collections.Counter())[r.get('candidate_source','unknown')]+=1
  root=Path(r['out']);log=root.parent/('guard-'+root.name+'.stderr.txt');sectors=[]
  for x in re.findall(pattern,log.read_text() if log.exists() else ''):
   item=dict(zip(['mode','period','n','requested','pairs','success','reused','analyses','factors','rhs'],map(int,x[:10])))
   item['shift']=float(x[10]);item['seconds']=float(x[11]);sectors.append(item)
  if sectors:
   shifts={}
   for s in sectors:
    key=(s['mode'],s['period'],s['n'])
    if s['reused']:
     assert r['solver']=='hsolve-reuse' and s['analyses']==s['factors']==0,(r,s)
     assert key in shifts and s['shift']==shifts[key],(r,s,shifts)
    else:shifts[key]=s['shift']
   work.append(dict(case=r['case'],out=r['out'],solver=r['solver'],inner_calls=len(sectors),inner_analyses=sum(x['analyses'] for x in sectors),inner_factorizations=sum(x['factors'] for x in sectors),inner_rhs=sum(x['rhs'] for x in sectors),reused_calls=sum(x['reused'] for x in sectors),requested_pair_sum=sum(x['requested'] for x in sectors),sectors=sectors))
expected={r['case']:r['expected_candidate'] for file in [p/'case-manifest.json',p38/'case-manifest.json',p/'extra-case-manifest-v2.json'] for r in read(file)};expected['target-on-mode-expansion']='iterative';small=[]
for r in runs:
 if r['case'] not in expected or r['solver'] not in ['hsolve-direct','hsolve-reuse']:continue
 assert r['valid'] and r['completeness']=='complete'
 assert r['candidate_source']==expected[r['case']],r
 if r['case']!='certificate-off':assert r['certificate']['passed'] and r['certificate']['method']=='exact'
 small.append(dict(case=r['case'],solver=r['solver'],candidate_source=r['candidate_source'],max_eta=r['max_eta'],certificate=r['certificate']))
assert len(small)==34
assert read(p/'diagnostic-qualified.json')['qualified']
contracts=read(p/'contract-check-results.json');assert len(contracts)==18
budget=read(p/'budget-check-results.json');assert len(budget['profiles'])==4
extra=read(p/'extra-check-results-v2.json');assert extra['qualified']
regression={}
for variant in ['direct','reuse']:
 full=p/('full-'+variant);regrows=read(full/'results.json');counts=collections.Counter();failures=[];skips=[]
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
 regression[variant]=dict(summary=read(full/'summary.json'),totals=dict(counts),failures=failures,skips=skips)
production={str(repo/'build/release'/n):digest(repo/'build/release'/n) for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']}
expected_production={'hsolve':'045409af0138ab363106ab5d7483260b69a260ed2212bbbbbc29becb70bfc377','hsolve-mpi':'d46e2a435891f138f64acb679cda509285a6cc308756f2158fe461b4af2b6648','libhsolve.a':'9b5e0b567830e5f22f5c01796f1084f7ea49f5860be2aa89ac3bd8312b522fd1','libhsolve_blashook.so':'150ae2ed9beb3a06f26ee6b6670877e3048d2513d09441b122257a70fff09056'}
assert {Path(k).name:v for k,v in production.items()}==expected_production
source=digest(repo/'src/driver/definite.cpp');assert source=='f40ca695157d9334626b7928837716305c30439d257e0636ce9681e838d122d4'
builds={}
for v in ['control','direct','reuse']:
 b=read(p/f'{v}-build-hashes.json');assert production==b['production_before']==b['production_after']
 for category in ['sources','experimental']:
  for name,sha in b[category].items():assert digest(p/name)==sha,(v,name)
 assert digest(Path(b['input_library']['path']))==b['input_library']['sha256'];builds[v]=b
dependencies={str(p38/'adaptive_bloch.hpp'):digest(p38/'adaptive_bloch.hpp')}
assert dependencies[str(p38/'adaptive_bloch.hpp')]==read(p38/'adaptive-build-hashes.json')['sources']['adaptive_bloch.hpp']
monitor=read(p/'screen-monitor-result.json');recheck=read(p/'recheck/screen-monitor-result.json');recheck2=read(p/'recheck2/screen-monitor-result.json');recheck3=read(p/'recheck3/screen-monitor-result.json')
qualified={};performance={};references=[];batch_qualification={};performance_sources={};batch_performance={}
for batch,mon in [('p39-screen',monitor),('p39-recheck',recheck),('p39-recheck2',recheck2),('p39-recheck3',recheck3)]:
 batch_qualification[batch]={};batch_performance[batch]={}
 if not mon.get('rows'):continue
 by_out={r['out']:r for r in mon['rows']}
 for case in sorted({r['case'] for r in mon['rows']}):
  rows=[r for r in runs if tag(r)==batch and r['case']==case];c=collections.Counter(r['solver'] for r in rows)
  ok=len(c)==8 and all(n==5 for n in c.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
  batch_qualification[batch][case]=ok
  qualified.setdefault(case,False)
  if not ok:continue
  stats={}
  for solver in c:
   selected=[r for r in rows if r['solver']==solver];values=[r['solver_s'] for r in selected]
   stats[solver]=dict(median_s=statistics.median(values),min_s=min(values),max_s=max(values),valid=len(selected),max_eta=max(r['max_eta'] for r in selected))
  for solver in stats:stats[solver]['time_over_slepc']=stats[solver]['median_s']/stats['slepc']['median_s']
  batch_performance[batch][case]=stats
  # A retry replaces only an invalid full group, never individual samples or
  # an already-qualified group. Selection is by validity, never by speed.
  if not qualified[case]:qualified[case]=True;performance[case]=stats;performance_sources[case]=batch
assert set(batch_qualification['p39-recheck'])<= {'syn-multiplicity-complex-1e4','syn-ghep-zero-cluster-complex-1e4','yee-bloch-1e4'}
assert set(batch_qualification['p39-recheck2'])<= {'syn-multiplicity-complex-1e4','syn-ghep-zero-cluster-complex-1e4'}
assert set(batch_qualification['p39-recheck3'])<= {'syn-multiplicity-complex-1e4'}
for row in runs:
 if row['solver']=='slepc':
  r=read(Path(row['out'])/'report.json');assert r.get('petsc_scalar_type')=='complex128' and r.get('factor_pc_type')=='lu'
  references.append(dict(out=row['out'],config=row['config'],scope=row['config_scope'],source=row['config_source']))
phase_medians={}
for case,batch in performance_sources.items():
 selected=[r for r in runs if r['case']==case and tag(r)==batch]
 phase_medians[case]={}
 for solver in performance[case]:
  rows=[r for r in selected if r['solver']==solver];keys=set().union(*(r.get('phases',{}) for r in rows));phases={}
  for key in keys:
   values=[r.get('phases',{}).get(key) for r in rows];values=[v for v in values if isinstance(v,(int,float))]
   if values:phases[key]=statistics.median(values)
  phase_medians[case][solver]=phases
result=dict(round='P39',host='gpu02',goal_achieved=False,production_adopted=False,full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),groups=groups,source_counts=sources,small_cases=small,contracts=contracts,budget=budget,extra_checks=extra,modal_work=work,regression=regression,production_hashes=production,production_source_sha256=source,builds=builds,extra_dependency_hashes=dependencies,monitor=monitor,recheck_monitor=recheck,recheck2_monitor=recheck2,recheck3_monitor=recheck3,batch_qualification=batch_qualification,batch_performance=batch_performance,performance_sources=performance_sources,qualified_cases=qualified,performance=performance,phase_medians=phase_medians,references=references,guards={str(f.relative_to(p)):read(f) for f in p.rglob('*-guard.json')},caveats=['Shared-core diagnostic times are not performance evidence.','Direct and cached sector Lanczos preserve original-pencil residual/rank checks and exact inertia certification.','Every cached factor keeps its actual shift; no global state survives a candidate-construction call.','Cache budget divides remaining allowance across every sector; original factor memory checks remain active.','The zero-filter option declines this optimization and takes the ordinary path.','Outer factor statistics exclude inner sector solves; their costs remain in parent time_total_s/time_iterate_s and detailed stderr records.','The two physical photonic inputs have incomplete external references.','No sparse matrix is densified by the solver. Dense full-spectrum references are only for small tests of order <=420.','The initial budget checker failed before compilation because its link-object assumption was wrong; budget_check_v2 fixes only the harness. Both records are retained.','The initial extra test requested k=20 beyond the recognizer size guard (32<44), so all three correct solves used the ordinary path and its coverage assertion failed. v2 requests k=14 within the guard, forcing all initial sectors to expand.', 'Frozen private native libraries require previous P33-P38 dependencies; production P29 remains unchanged.'])
(p/'collected.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['full_solve_attempts','full_solve_valid','valid_completeness','qualified_cases']}));print(json.dumps(dict(regression={k:v['totals'] for k,v in regression.items()},source_counts=sources)))
