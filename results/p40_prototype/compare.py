import json,os,sys,time
from pathlib import Path
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.bench import compare
p=Path('/tmp/os2026-p40');ref=Path('/tmp/os2026-p28/ref-complex')
variants={f'hsolve-{family}-t{threads}':{} for family in ['dd','reuse'] for threads in [1,2,4,8,16]}
compare.HSOLVE_VARIANTS.update(variants);compare.SOLVERS=(*variants,'slepc')
old_cmd,old_run,old_mpi,old_guard=compare.hsolve_command,compare.run_once,compare.mpiexec_command,compare.guarded
def command(c,solver,out,ncores,args,target):
 a=old_cmd(c,solver,out,ncores,args,target);family,threadpart=solver.removeprefix('hsolve-').split('-t');threads=int(threadpart);a[0]=str(p/('hsolve-'+family));a[a.index('--threads')+1]=str(threads)
 a+=['--log',str(out.parent/('events-'+out.name+'.jsonl'))]
 if os.environ.get('P40_MEMORY_BUDGET_GB'):a+=['--memory-budget-gb',os.environ['P40_MEMORY_BUDGET_GB']]
 return a
def guarded(cmd,summary,cores,mem_gb,timeout,threads,exclusive):
 if cmd[0] in [str(p/'hsolve-dd'),str(p/'hsolve-reuse')]:threads=int(cmd[cmd.index('--threads')+1])
 return old_guard(cmd,summary,cores,mem_gb,timeout,threads,exclusive)
def mpi(*args,**kwargs):
 kwargs['ref_env']=ref
 return ['env',f'LD_LIBRARY_PATH={ref}/lib','PYTHONNOUSERSITE=1']+old_mpi(*args,**kwargs)
def run(solver,c,tgt,out,*args,**kwargs):
 started=time.monotonic();row=old_run(solver,c,tgt,out,*args,**kwargs);ended=time.monotonic();row.update(case=c.name,out=str(out),started_monotonic=started,ended_monotonic=ended)
 if os.environ.get('P40_MEMORY_BUDGET_GB'):row['explicit_memory_budget_gb']=float(os.environ['P40_MEMORY_BUDGET_GB'])
 if solver in variants:
  row.update(config=solver,config_scope='case',config_source='Frozen P37 dd or P39 reuse; same available 16 cores; thread cap is the only sweep variable',requested_threads=int(solver.rsplit('-t',1)[1]))
  f=out/'report.json'
  if f.exists():
   rep=json.loads(f.read_text());row['candidate_source']=rep.get('candidate_source');row['certificate']=rep.get('certificate')
 else:row.update(reference_env=str(ref),reference_scalar='complex128')
 with (p/'runs.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 return row
compare.hsolve_command,compare.run_once,compare.mpiexec_command,compare.guarded=command,run,mpi,guarded
raise SystemExit(compare.main())
