import hashlib,json,shlex,shutil,subprocess,sys
from pathlib import Path
repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release';p=Path('/tmp/os2026-p38');old=Path('/tmp/os2026-p37')
variant=sys.argv[1];assert variant in ['control','partial']
tracked=[b/n for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']]
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f):digest(f) for f in tracked};commands=[]
def command(target):
 a=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands',target],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
 if a[:2]==[':','&&']:assert a[-2:]==['&&',':'];a=a[2:-2]
 assert not any(x in ['&&','||',';'] for x in a);return a
def run(a):
 commands.append(a);(p/f'{variant}-build-commands.json').write_text(json.dumps(commands,indent=2)+'\n');subprocess.run(a,cwd=b,check=True)
obj=p/variant/'definite.cpp.o';obj.parent.mkdir(exist_ok=True)
a=command('CMakeFiles/hsolve.dir/src/driver/definite.cpp.o')
for opt,val in [('-c',p/'definite.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:a[a.index(opt)+1]=str(val)
a+=['-DP38_PARTIAL_BLOCH='+str(int(variant=='partial'))];run(a)
lib=p/f'libhsolve-{variant}.a';shutil.copy2(old/'libhsolve-control.a',lib);run(['ar','r',str(lib),str(obj)])
a=command('hsolve');a=[str(lib) if x=='libhsolve.a' else x for x in a];a[a.index('-o')+1]=str(p/f'hsolve-{variant}')
for i,x in enumerate(a):
 if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(p/f'{variant}-link.d')
run(a)
for name,source in [('hsolve-base',b/'hsolve'),('hsolve-native',old/'hsolve-control'),('hsolve-scalar',old/'hsolve-scalar'),('hsolve-dd',old/'hsolve-dd')]:
 if not (p/name).exists():shutil.copy2(source,p/name)
 assert digest(p/name)==digest(source)
after={str(f):digest(f) for f in tracked};assert before==after
(p/f'{variant}-build-hashes.json').write_text(json.dumps(dict(production_before=before,production_after=after,experimental={n:digest(p/n) for n in [f'hsolve-{variant}',f'libhsolve-{variant}.a','hsolve-base','hsolve-native']},input_library=dict(path=str(old/'libhsolve-control.a'),sha256=digest(old/'libhsolve-control.a')),sources={name:digest(p/name) for name in ['definite.cpp','partial_bloch.hpp']}),indent=2)+'\n')
print(variant,'built; production unchanged',flush=True)
