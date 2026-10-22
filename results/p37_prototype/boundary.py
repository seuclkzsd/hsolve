import hashlib,json,subprocess
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p37');repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release'
manifest=json.loads((p/'dd-manifest.json').read_text());outputs={r['id']:r for r in map(json.loads,(p/'dd-check.stdout').read_text().splitlines())}
candidates=[x for x in manifest if not x.get('singular') and outputs[x['id']].get('analyses')==1]
selected=candidates[::max(1,len(candidates)//8)][:8]
assert len(selected)==8
out=p/'boundary';out.mkdir(exist_ok=True)
selected=[{**x,'prefix':str(out/x['id'])} for x in selected]
(p/'boundary-manifest.json').write_text(json.dumps(selected,indent=2)+'\n')
commands=json.loads((p/'dd-build-commands.json').read_text());compile=commands[3].copy();link=commands[4].copy();obj=p/'boundary_check.cpp.o'
for opt,val in [('-c',p/'boundary_check.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:compile[compile.index(opt)+1]=str(val)
link=[str(obj) if v==str(p/'check-dd.cpp.o') else v for v in link];link[link.index('-o')+1]=str(p/'boundary-check')
link=['-Wl,--dependency-file='+str(p/'boundary-link.d') if v.startswith('-Wl,--dependency-file=') else v for v in link]
(p/'boundary-build-commands.json').write_text(json.dumps([compile,link],indent=2)+'\n')
for cmd in [compile,link]:subprocess.run(cmd,cwd=b,check=True)
with (p/'boundary-check.stdout').open('w') as stdout,(p/'boundary-check.stderr').open('w') as stderr:
 subprocess.run([str(p/'boundary-check'),str(p/'boundary-manifest.json')],stdout=stdout,stderr=stderr,check=True)
def loaded(path):
 a=sp.load_npz(path).astype(np.complex128).tocsr();a.sum_duplicates();a.sort_indices()
 if bool(sp.triu(a,k=1).nnz)!=bool(sp.tril(a,k=-1).nnz):a=a+a.getH()-sp.diags(a.diagonal())
 if (a-a.getH()).nnz:a=(a*.5+a.getH()*.5).tocsr()
 return a.astype(np.clongdouble)
matrices={x['id']:(loaded(x['a']),loaded(x['b']) if 'b' in x else None) for x in selected}
rows=[json.loads(s) for s in (p/'boundary-check.stdout').read_text().splitlines()]
assert len(rows)==320 and all(r['valid'] for r in rows)
for row in rows:
 if row['nonfinite']:continue
 a,b=matrices[row['id']];a=a*np.longdouble(row['alpha']);b=(sp.eye(a.shape[0],dtype=np.clongdouble) if b is None else b)*np.longdouble(row['beta'])
 prefix=row['prefix'];x=np.load(prefix+'-x.npy').astype(np.clongdouble);rhs=np.load(prefix+'-rhs.npy').astype(np.clongdouble);r=np.load(prefix+'-r.npy').astype(np.clongdouble)
 oracle=rhs-(a@x+b@x);den=abs(rhs)+abs(a)@abs(x)+abs(b)@abs(x)
 ratio=float(np.max(abs(r-oracle)/np.maximum(den,np.finfo(np.longdouble).tiny)))
 row['ratio']=ratio;row['valid']=bool(np.isfinite(ratio) and ratio<=1e-16)
(p/'boundary-results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(r['valid'] for r in rows),[r for r in rows if not r['valid']]
hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ['boundary_check.cpp','boundary_check.cpp.o','boundary-check','band_backend.hpp','band_ldlh.cpp']}
(p/'boundary-build-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
summary=dict(checks=len(rows),valid=sum(r['valid'] for r in rows),vectorized=sum(r['vectorized'] for r in rows),fallback=sum(not r['vectorized'] for r in rows),nonfinite=sum(r['nonfinite'] for r in rows),max_ratio=max(r.get('ratio',0.) for r in rows))
(p/'boundary-qualified.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
