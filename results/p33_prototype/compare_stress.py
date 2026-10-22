import json,sys,time
from pathlib import Path
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools.bench import compare
p=Path('/tmp/os2026-p33');ref=Path('/tmp/os2026-p28/ref-complex')
variants={'hsolve-base':{'block_size':16},'hsolve-requested':{'block_size':16},'hsolve-requestedlu':{'block_size':16},'hsolve-counts':{},'hsolve-lucached':{},'hsolve-recovery':{},'hsolve-recoverylu':{}}
compare.HSOLVE_VARIANTS.update(variants);compare.SOLVERS=(*variants,'slepc')
old_cmd,old_run,old_mpi=compare.hsolve_command,compare.run_once,compare.mpiexec_command
def command(c,solver,out,ncores,args,target):
 a=old_cmd(c,solver,out,ncores,args,target);a[0]=str((Path('/tmp/os2026-p32') if solver in ['hsolve-counts','hsolve-lucached'] else p)/solver)
 if solver in ['hsolve-recovery','hsolve-recoverylu']:a[0]=str(p/'recovery-only'/('hsolve-requestedlu' if solver.endswith('lu') else 'hsolve-requested'))
 a+=['--log',str(out.parent/('events-'+out.name+'.jsonl'))]
 return a
def mpi(*args,**kwargs):
 kwargs['ref_env']=ref
 return ['env',f'LD_LIBRARY_PATH={ref}/lib','PYTHONNOUSERSITE=1']+old_mpi(*args,**kwargs)
def run(solver,c,tgt,out,*args,**kwargs):
 started=time.monotonic();row=old_run(solver,c,tgt,out,*args,**kwargs);ended=time.monotonic();row.update(case=c.name,out=str(out),started_monotonic=started,ended_monotonic=ended)
 if solver in variants:
  row.update(config=solver,config_scope='case',config_source='Frozen P29; explicit block_size=16 diagnostic' if solver=='hsolve-base' else 'P33 v2; explicit block_size=16 diagnostic')
  f=out/'report.json'
  if f.exists():
   rep=json.loads(f.read_text());row['candidate_source']=rep.get('candidate_source');row['certificate']=rep.get('certificate')
 else:row.update(reference_env=str(ref),reference_scalar='complex128')
 with (p/'runs.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 return row
compare.hsolve_command,compare.run_once,compare.mpiexec_command=command,run,mpi
raise SystemExit(compare.main())
