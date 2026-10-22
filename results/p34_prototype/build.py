import hashlib,json,shlex,shutil,subprocess
from pathlib import Path
repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release';p=Path('/tmp/os2026-p34');old=Path('/tmp/os2026-p33')
tracked=[b/n for n in ['hsolve','hsolve-mpi','libhsolve.a','libhsolve_blashook.so']]
def digest(f):return hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f):digest(f) for f in tracked};commands=[]
def command(target):
 a=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands',target],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
 if a[:2]==[':','&&']:assert a[-2:]==['&&',':'];a=a[2:-2]
 assert not any(x in ['&&','||',';'] for x in a);return a
def run(a):
 commands.append(a);(p/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n');subprocess.run(a,cwd=b,check=True)
objects={}
for variant,project in [('guarded',0),('projected',1)]:
 obj=p/variant/'definite.cpp.o';obj.parent.mkdir(exist_ok=True)
 a=command('CMakeFiles/hsolve.dir/src/driver/definite.cpp.o')
 for opt,val in [('-c',p/'definite.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:a[a.index(opt)+1]=str(val)
 a+=['-DP34_PROJECT_RESCUE='+str(project)];run(a);objects[variant]=obj
for variant,lib_source,obj in [('guarded',b/'libhsolve.a',objects['guarded']),('projected',b/'libhsolve.a',objects['projected']),('projectednative',old/'libhsolve-requested.a',objects['projected']),('projectedlu',old/'libhsolve-requestedlu.a',objects['projected'])]:
 lib=p/f'libhsolve-{variant}.a';shutil.copy2(lib_source,lib);run(['ar','r',str(lib),str(obj)])
 a=command('hsolve');a=[str(lib) if x=='libhsolve.a' else x for x in a];a[a.index('-o')+1]=str(p/f'hsolve-{variant}')
 for i,x in enumerate(a):
  if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(p/f'{variant}-link.d')
 run(a)
shutil.copy2(b/'hsolve',p/'hsolve-base');shutil.copy2(old/'hsolve-requested',p/'hsolve-native');shutil.copy2(old/'hsolve-requestedlu',p/'hsolve-lu')
after={str(f):digest(f) for f in tracked};assert before==after
(p/'build-hashes.json').write_text(json.dumps(dict(production_before=before,production_after=after,experimental={f.name:digest(f) for f in p.glob('hsolve-*')},input_libraries={str(f):digest(f) for f in [b/'libhsolve.a',old/'libhsolve-requested.a',old/'libhsolve-requestedlu.a']},source=digest(p/'definite.cpp')),indent=2)+'\n');print('P34 built four private variants; production unchanged',flush=True)
