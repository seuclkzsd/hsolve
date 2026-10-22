import collections,hashlib,json,re,statistics
from pathlib import Path
p=Path('/tmp/os2026-p40');v=p/'v3';repo=Path('/tmp/os2026-p10-repair.9doyhO')
def read(f):return json.loads(f.read_text())
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for block in iter(lambda:src.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def tag(r):return Path(r['out']).relative_to(repo/'results/raw').parts[0]
def lines(f):return [json.loads(s) for s in f.read_text().splitlines()]
thread=lines(p/'runs.jsonl');candidate=lines(v/'candidate-runs.jsonl');runs=thread+candidate
assert len(thread)==297 and len({r['out'] for r in runs})==len(runs)
assert all(r['valid'] for r in runs),[r for r in runs if not r['valid']]
groups={};sources={};enclosures=[]
for r in runs:
 g=groups.setdefault(tag(r),{}).setdefault(r['solver'],dict(attempts=0,valid=0));g['attempts']+=1;g['valid']+=int(bool(r['valid']))
 if r['solver'].startswith('hsolve'):
  sources.setdefault(r['solver'],collections.Counter())[r.get('candidate_source','unknown')]+=1
  if r['solver']=='hsolve-enclosed':
   root=Path(r['out']);f=root.parent/('guard-'+root.name+'.stderr.txt')
   raw=f.read_text() if f.exists() else ''
   counts=[tuple(map(int,x)) for x in re.findall(r'P40 residual_enclosure accepts=(\d+) fallbacks=(\d+)',raw)]
   # Counters are cumulative within one backend; a decrease starts a new backend.
   accepts=fallbacks=0;previous=(0,0)
   for a,b in counts:
    if a<previous[0] or b<previous[1]:previous=(0,0)
    accepts+=a-previous[0];fallbacks+=b-previous[1];previous=(a,b)
   enclosures.append(dict(case=r['case'],out=r['out'],records=len(counts),counter_estimate_accepts=accepts,counter_estimate_fallbacks=fallbacks,raw_counters=counts))
expected={r['case']:r['expected_candidate'] for base in [Path('/tmp/os2026-p39'),Path('/tmp/os2026-p38')] for r in read(base/'case-manifest.json')}
expected.update({'target-on-mode-expansion':'iterative','target-on-mode-expansion-v2':'partial_bloch_translation'})
small=[]
for r in candidate:
 if r['case'] in expected:
  assert r['valid'] and r['completeness']=='complete' and r['candidate_source']==expected[r['case']]
  if r['case']!='certificate-off':assert r['certificate']['passed'] and r['certificate']['method']=='exact'
  small.append({k:r.get(k) for k in ['case','solver','candidate_source','max_eta','certificate']})
assert len(small)==34
assert read(v/'diagnostic-qualified.json')==dict(attempts=194,valid=194,qualified=True)
contracts=read(v/'contract-check-results.json');assert len(contracts)==18
regression={}
for variant in ['control','enclosed']:
 full=v/('full-'+variant);regrows=read(full/'results.json');counts=collections.Counter();failures=[];skips=[]
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
assert {Path(k).name:s for k,s in production.items()}==expected_production
source=digest(repo/'src/driver/definite.cpp');assert source=='f40ca695157d9334626b7928837716305c30439d257e0636ce9681e838d122d4'
frozen=read(p/'frozen-hashes.json')
assert frozen['production']==expected_production
for name,item in frozen['experimental'].items():
 assert digest(p/name)==item['sha256']==digest(Path(item['source']))
for name,sha in frozen['sources'].items():assert digest(p/name)==sha
for name,src in [('hsolve-dd',Path('/tmp/os2026-p37/hsolve-dd')),('hsolve-native',Path('/tmp/os2026-p39/hsolve-reuse')),('hsolve-base',repo/'build/release/hsolve')]:assert digest(v/name)==digest(src)
assert (v/'residual_enclosure.inc').read_text().strip() in (v/'band_backend.hpp').read_text()
builds={};numerics={}
for version,base in [('v1',p),('v2',p/'v2'),('v3',v)]:
 builds[version]={};numerics[version]={}
 for variant in ['control','enclosed']:
  b=read(base/f'{variant}-build-hashes.json');assert production==b['production_before']==b['production_after']
  for category in ['sources','experimental']:
   for name,sha in b[category].items():assert digest(base/name)==sha,(version,variant,name)
  assert digest(Path(b['input_library']['path']))==b['input_library']['sha256'];builds[version][variant]=b
  linear=read(base/f'{variant}-check-results.json');assert len(linear)==1540 and all(r['valid'] for r in linear)
  outputs=lines(base/f'{variant}-check.stdout');manifest=read(base/f'{variant}-manifest.json')
  numerics[version][variant]=dict(linear_checks=len(linear),valid=sum(r['valid'] for r in linear),max_eta=max(r['eta'] for r in linear),singular_rejections=sum(r.get('singular',False) for r in manifest),lazy_fallback_inputs=sum(r.get('analyses',0)>1 for r in outputs))
 for name in ['enclosure-qualified.json','boundary-qualified.json']:
  q=read(base/name);assert q['qualified'];numerics[version][name]=q
assembly=read(v/'assembly-check-results.json');assert len(assembly)==3 and all(r['qualified'] for r in assembly)
for r in assembly:assert digest(v/r['object'])==r['sha256']
for name in ['build-guard.json','linear-guard.json','boundary-v3-guard.json','diagnostic-guard.json','full-guard.json']:assert read(v/name)['returncode']==0
series=read(v/'candidate-series.json');performance={};phases={};batch_qualification={};thread_performance={}
monitor=read(p/'screen-monitor-result.json')
def summarize(rows):
 stats={}
 for solver in sorted({r['solver'] for r in rows}):
  selected=[r for r in rows if r['solver']==solver];values=[r['solver_s'] for r in selected]
  stats[solver]=dict(median_s=statistics.median(values),min_s=min(values),max_s=max(values),wall_median_s=statistics.median(r['wall_s'] for r in selected),solver_scopes=sorted({r['solver_s_scope'] for r in selected}),peak_rss_gib=max(r['peak_rss_gib'] for r in selected),valid=len(selected),max_eta=max(r['max_eta'] for r in selected))
 for solver in stats:stats[solver]['time_over_slepc']=stats[solver]['median_s']/stats['slepc']['median_s']
 return stats
by_out={r['out']:r for r in monitor.get('rows',[])};thread_qualification={}
for case in sorted({r['case'] for r in thread}):
 rows=[r for r in thread if r['case']==case];counts=collections.Counter(r['solver'] for r in rows)
 ok=len(counts)==11 and all(n==3 for n in counts.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
 thread_qualification[case]=ok
 if ok:thread_performance[case]=summarize(rows)
monitors={}
for batch in series['batches']:
 mon=read(Path(batch['monitor']));monitors[batch['tag']]=mon
 plan=read(Path(batch['monitor']).parent/'plan.json')
 for name,sha in plan['source_hashes'].items():assert digest(v/name)==sha
 by_out={r['out']:r for r in mon.get('rows',[])};batch_qualification[batch['tag']]={}
 for case in plan['cases']:
  rows=[r for r in candidate if r['case']==case and tag(r)==batch['tag']];counts=collections.Counter(r['solver'] for r in rows)
  ok=set(counts)==set(plan['solvers']) and all(n==5 for n in counts.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
  batch_qualification[batch['tag']][case]=ok
  if ok and case not in performance:
   assert series['qualified'][case]==batch['tag'];performance[case]=summarize(rows);phases[case]={}
   for solver in performance[case]:
    selected=[r for r in rows if r['solver']==solver];keys=set().union(*(r.get('phases',{}) for r in selected));values={}
    for key in keys:
     nums=[r.get('phases',{}).get(key) for r in selected];nums=[x for x in nums if isinstance(x,(int,float))]
     if nums:values[key]=statistics.median(nums)
    phases[case][solver]=values
assert set(performance)==set(series['qualified'])
references=[]
for r in runs:
 if r['solver']=='slepc':
  report=read(Path(r['out'])/'report.json');assert report.get('petsc_scalar_type')=='complex128' and report.get('factor_pc_type')=='lu'
  references.append(dict(out=r['out'],config=r['config'],scope=r['config_scope'],source=r['config_source']))
result=dict(round='P40',host='gpu02',goal_achieved=False,production_adopted=False,full_solve_attempts=len(runs),full_solve_valid=sum(bool(r['valid']) for r in runs),valid_completeness=dict(collections.Counter(r['completeness'] for r in runs)),thread_sweep_attempts=len(thread),candidate_attempts=len(candidate),groups=groups,source_counts=sources,small_cases=small,contracts=contracts,enclosure_counters=enclosures,numerics=numerics,assembly=assembly,regression=regression,production_hashes=production,production_source_sha256=source,builds=builds,thread_monitor=monitor,thread_qualification=thread_qualification,thread_performance=thread_performance,series=series,candidate_monitors=monitors,batch_qualification=batch_qualification,performance=performance,phase_medians=phases,references=references,guards={str(f.relative_to(p)):read(f) for f in p.rglob('*-guard.json')},caveats=['Diagnostic timings are not performance evidence.','Thread grid has only 3 repetitions; contaminated full groups excluded; exploratory negative result only.','Formal comparisons use the first qualified full 30-run case group, never the fastest run.','Original eigenpair residual, rank and exact inertia certificate remain active. Internal acceptance retains 1e-12 and falls back to long double.','v1 numeric checks passed but implicit FMA contraction did not match the proof. v2 disables contraction in the enclosure function; v3 also checks each worker mode.','v3 initial boundary harness omitted omp.h. The next harness expected worker FP modes to persist across OpenMP regions; a probe proved libgomp resets them. Final harness verifies the observed reset and preserves caller controls. This is not coverage of an abnormal mode inside a persistent worker.','Enclosure counters are cumulative per backend. Counter estimates may undercount consecutive backends with nondecreasing counters; raw sequences are authoritative.','Parent phase times include inner sector work; parent factor counters alone do not.','Two photonic inputs have incomplete external spectrum references.','Solver never densifies sparse matrices; full dense oracles are limited to small test inputs.','Periodic process sampling cannot prove exclusive physical ownership or capture every short-lived or migrating thread.','Private candidates require P29 and frozen P33-P39 dependencies; production P29 unchanged.'])
(p/'collected.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['full_solve_attempts','full_solve_valid','valid_completeness','thread_qualification','series']}));print(json.dumps({k:v['totals'] for k,v in regression.items()}))
