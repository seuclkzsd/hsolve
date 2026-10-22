import hashlib,json,shlex,subprocess,sys
from pathlib import Path
p=Path('/tmp/os2026-p34');repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release';variant=sys.argv[1]
assert variant in ['projected','shifted','carried','carriednative','bounded','boundednative','accepted','acceptednative']
out=p/('regression-'+variant);out.mkdir(exist_ok=True)
lib=p/f'libhsolve-{variant}.a';targets=['test_driver_solve','test_driver_cluster','test_driver_windows','test_certint','test_certint_fix','test_certfast','test_certfast_fix','test_certfast_single','test_certcost_faults','test_membudget','test_membudget_single','test_separable_curl','test_blocktune_driver','test_anaint_driver','test_anaint_fix_shift']
results=[];commands=[]
for target in targets:
 a=shlex.split(subprocess.run(['ninja','-C',str(b),'-t','commands',target],check=True,capture_output=True,text=True).stdout.splitlines()[-1])
 if a[:2]==[':','&&']:assert a[-2:]==['&&',':'];a=a[2:-2]
 assert not any(x in ['&&','||',';'] for x in a),target
 assert 'libhsolve.a' in a,target
 a=[str(lib) if x=='libhsolve.a' else x for x in a];a[a.index('-o')+1]=str(out/target)
 for i,x in enumerate(a):
  if x.startswith('-Wl,--dependency-file='):a[i]='-Wl,--dependency-file='+str(out/(target+'-link.d'))
 commands.append(a);(out/'link-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 subprocess.run(a,cwd=b,check=True)
 cmd=[str(out/target),'--gtest_output=json:'+str(out/(target+'.json'))]
 with (out/(target+'.log')).open('w') as log:
  try:r=subprocess.run(cmd,cwd=b,stdout=log,stderr=subprocess.STDOUT,timeout=180);rc=r.returncode
  except subprocess.TimeoutExpired:rc=124
 data=json.loads((out/(target+'.json')).read_text()) if (out/(target+'.json')).exists() else {}
 row=dict(target=target,returncode=rc,tests=data.get('tests'),failures=data.get('failures'),disabled=data.get('disabled'),errors=data.get('errors'),time=data.get('time'));results.append(row)
 (out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
print(json.dumps(dict(variant=variant,success=all(x['returncode']==0 for x in results),library_sha256=hashlib.sha256(lib.read_bytes()).hexdigest())),flush=True)
raise SystemExit(0 if all(x['returncode']==0 for x in results) else 1)
