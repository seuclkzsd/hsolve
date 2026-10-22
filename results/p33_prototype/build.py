import hashlib,json,shlex,shutil,subprocess,sys
from pathlib import Path
repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release';p=Path('/tmp/os2026-p33')
variant=sys.argv[1];assert variant in ['requested','requestedlu'];flag='-DP33_USE_LU='+str(int(variant=='requestedlu'))
tracked=[b/name for name in ['libhsolve.a','hsolve','hsolve-mpi','libhsolve_blashook.so']]
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f):digest(f) for f in tracked};commands=[]
def command(target):
 a=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands',target],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
 if a[:2]==[':','&&']:assert a[-2:]==['&&',':'];a=a[2:-2]
 assert not any(x in ['&&','||',';'] for x in a);return a
def run(a):
 commands.append(a);(p/f'{variant}-build-commands.json').write_text(json.dumps(commands,indent=1)+'\n');subprocess.run(a,cwd=b,check=True)
def compile(source,obj):
 a=command('CMakeFiles/hsolve.dir/src/driver/solver.cpp.o')
 for opt,val in [('-c',source),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:a[a.index(opt)+1]=str(val)
 a+=['-march=native',flag,'-DP33_LU_SIMD=1'];run(a)
obj=p/(variant+'-objects')/'solver.cpp.o';obj.parent.mkdir(exist_ok=True);compile(p/'solver.cpp',obj);steps_obj=p/(variant+'-objects')/'steps.cpp.o';compile(p/'steps.cpp',steps_obj)
lib=p/f'libhsolve-{variant}.a';shutil.copy2(b/'libhsolve.a',lib);run(['ar','r',str(lib),str(obj),str(steps_obj)])
a=command('hsolve');a=[str(lib) if x=='libhsolve.a' else x for x in a];a[a.index('-o')+1]=str(p/f'hsolve-{variant}')
for i,x in enumerate(a):
 if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(p/f'{variant}-link.d')
run(a);shutil.copy2(b/'hsolve',p/'hsolve-base')
obj=p/f'check-{variant}.cpp.o';compile(p/'check.cpp',obj)
a=command('bench_factspeed_factor');objects=[x for x in a if x.endswith('.cpp.o')];assert len(objects)==1
a=[str(obj) if x in objects else x for x in a];a[a.index('-o')+1]=str(p/f'backend-check-{variant}')
for i,x in enumerate(a):
 if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(p/f'check-{variant}-link.d')
run(a);after={str(f):digest(f) for f in tracked};assert before==after
(p/f'{variant}-build-hashes.json').write_text(json.dumps(dict(production_before=before,production_after=after,experimental={n:digest(p/n) for n in [f'hsolve-{variant}',f'libhsolve-{variant}.a',f'backend-check-{variant}','hsolve-base']}),indent=2)+'\n')
print(variant,'built; production unchanged',flush=True)
