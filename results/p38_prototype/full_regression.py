import hashlib,json,os,shlex,subprocess,sys
from pathlib import Path
p=Path('/tmp/os2026-p38');repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release'
variant=sys.argv[1];assert variant in ['adaptive']
out=p/('full-'+variant);out.mkdir(exist_ok=True)
lib=b/'libhsolve.a' if variant=='base' else p/f'libhsolve-{variant}.a'
cli=b/'hsolve' if variant=='base' else p/f'hsolve-{variant}'
commands=[];results=[]
def command(target):
 a=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands',target],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
 if a[:2]==[':','&&']:assert a[-2:]==['&&',':'];a=a[2:-2]
 assert not any(x in ['&&','||',';'] for x in a);return a
def build(a):
 commands.append(a);(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 subprocess.run(a,cwd=b,check=True)
def link(target):
 a=command(target);assert 'libhsolve.a' in a,target
 a=[str(lib) if x=='libhsolve.a' else x for x in a]
 if target in ['test_gpu_hook','test_asmkern_fix_exehook']:
  source=f'CMakeFiles/{target}.dir/tests/cpp/{target}.cpp.o';obj=out/(target+'.cpp.o')
  c=command(source)
  assert any(x.startswith('-DHSOLVE_HOOKED_CLI=') for x in c)
  c=[f'-DHSOLVE_HOOKED_CLI="{cli}"' if x.startswith('-DHSOLVE_HOOKED_CLI=') else x for x in c]
  for opt,val in [('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:c[c.index(opt)+1]=str(val)
  build(c);assert source in a;a=[str(obj) if x==source else x for x in a]
 exe=out/target;a[a.index('-o')+1]=str(exe)
 for i,x in enumerate(a):
  if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(out/(target+'-link.d'))
 build(a);return exe
env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',HSOLVE_TEST_GPU_DEVICE='',CUDA_VISIBLE_DEVICES='')
def run(label,cmd,extra=None,gtest=True,timeout=180):
 args=[str(x) for x in cmd]
 if gtest:args+=['--gtest_output=json:'+str(out/(label+'.json'))]
 e=env|dict(extra or {});commands.append(dict(run=args,environment={k:e.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_THREAD_LIMIT','OMP_PROC_BIND','OMP_PLACES','HSOLVE_TEST_OMP_BOUND','CUDA_VISIBLE_DEVICES']}))
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 with (out/(label+'.log')).open('w') as log:
  try:r=subprocess.run(args,cwd=b,env=e,stdout=log,stderr=subprocess.STDOUT,timeout=timeout);rc=r.returncode
  except subprocess.TimeoutExpired:rc=124
 f=out/(label+'.json');data=json.loads(f.read_text()) if f.exists() else {}
 row=dict(target=label,returncode=rc,tests=data.get('tests'),failures=data.get('failures'),disabled=data.get('disabled'),errors=data.get('errors'),time=data.get('time'))
 results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
targets=sorted(f.stem for f in (repo/'tests/cpp').glob('test_*.cpp'))
(out/'targets.json').write_text(json.dumps(targets,indent=2)+'\n')
for target in targets:run(target,[link(target)])
run('short-team',[out/'test_asmkern_fix','--gtest_filter=AsmkernFixShortTeam.*'],{'OMP_THREAD_LIMIT':'2'})
run('bound-affinity',[out/'test_gpu','--gtest_filter=GpuAffinityBound.*'],{'OMP_PROC_BIND':'close','OMP_PLACES':'cores','HSOLVE_TEST_OMP_BOUND':'1'})
mpi='/share/home/linzihan/envs/os2026-ref/bin/mpiexec';mpi_flags=['--oversubscribe','--bind-to','none']
test_mpi=link('test_mpi_session')
for ranks in [1,2,3,5]:run('mpi-ranks'+str(ranks),[mpi,'-n',str(ranks)]+mpi_flags+[test_mpi],timeout=600)
mpi_cli=link('hsolve-mpi')
run('mpi-cli-helper-log',['cmake','-DMPIEXEC='+mpi,'-DMPI_NUMPROC_FLAG=-n','-DMPI_FLAGS='+';'.join(mpi_flags),'-DHSOLVE_MPI='+str(mpi_cli),'-DTEST_DIR='+str(out/'mpi-cli-output'),'-P',repo/'tests/cmake/mpi_cli_failure.cmake'],{'OMP_NUM_THREADS':'1'},gtest=False,timeout=60)
summary=dict(variant=variant,library_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),ordinary_targets=len(targets),invocations=len(results),success=all(x['returncode']==0 for x in results))
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
raise SystemExit(0 if summary['success'] else 1)
