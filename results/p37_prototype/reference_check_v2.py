import hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.eval import common,evaluate
p=Path('/tmp/os2026-p37');repo=Path('/tmp/os2026-p10-repair.9doyhO');b=repo/'build/release';data=Path('~/os2026/data')
common.require_guard('P37 reference-window check')
manifest=[];details=[]
for name in ['yee-photonic-rods-1e4','yee-photonic-spheres-1e4']:
 c=cio.load_case(name,root=data);ref=cio.load_ref(name,root=data);assert ref is not None and ref.eigenvectors is not None
 tgt=common.target(c);assert tgt['mode']=='nearest';tol=common.tol(c);norms=evaluate.estimate_norms(c.A,c.B)
 w=np.asarray(ref.eigenvalues).real;distance=np.sort(abs(w-tgt['sigma']));rk=distance[tgt['k']-1]
 tie=10*tol*(norms.scale+abs(tgt['sigma'])+rk);outside=distance[distance>rk+tie]
 radius=float((rk+outside[0])*.5) if outside.size else float(rk+max(1e-6*norms.scale,.1*rk))
 lower,upper=tgt['sigma']-radius,tgt['sigma']+radius;inside=(w>lower)&(w<upper)
 vals=w[inside];vec=np.asarray(ref.eigenvectors)[:,inside].copy();assert vals.size>=tgt['k']
 bv=vec if c.B is None else c.B@vec;d=np.real(np.sum(vec.conj()*bv,axis=0));assert np.all(d>0)
 vec/=np.sqrt(d);bv=vec if c.B is None else c.B@vec
 orth=float(np.linalg.norm(vec.conj().T@bv-np.eye(vals.size),2));metrics=evaluate.pair_metrics(c.A,c.B,vals,vec,norms,1e-11)
 eta=max(x['backward_error'] for x in metrics);assert eta<=1e-11 and orth<=1e-6,(name,eta,orth)
 row=dict(case=name,a=str(c.path/'A.npz'),lower=lower,upper=upper,reference_count=int(vals.size))
 if c.B is not None:row['b']=str(c.path/'B.npz')
 manifest.append(row)
 details.append(dict(**row,reference_kind=ref.info.get('kind'),reference_was_complete=ref.info.get('complete',False),reference_original_count=int(w.size),target=tgt,max_eta=eta,b_orthogonality=orth,scale=norms.scale,selected_eigenvalues=vals.tolist(),dense_conversion=False))
(p/'reference-count-manifest-v2.json').write_text(json.dumps(manifest,indent=2)+'\n')
commands=json.loads((p/'dd-build-commands.json').read_text());compile=commands[3].copy();link=commands[4].copy();obj=p/'reference_count_v2.cpp.o'
for opt,val in [('-c',p/'reference_count_v2.cpp'),('-o',obj),('-MF',str(obj)+'.d'),('-MT',obj)]:compile[compile.index(opt)+1]=str(val)
link=[str(obj) if v==str(p/'check-dd.cpp.o') else v for v in link];link[link.index('-o')+1]=str(p/'reference-count-v2')
link=['-Wl,--dependency-file='+str(p/'reference-count-v2-link.d') if v.startswith('-Wl,--dependency-file=') else v for v in link]
(p/'reference-build-commands-v2.json').write_text(json.dumps([compile,link],indent=2)+'\n')
for cmd in [compile,link]:subprocess.run(cmd,cwd=b,check=True)
with (p/'reference-count-v2.stdout').open('w') as out,(p/'reference-count-v2.stderr').open('w') as err:subprocess.run([str(p/'reference-count-v2'),str(p/'reference-count-manifest-v2.json')],stdout=out,stderr=err,check=True)
counts=[json.loads(s) for s in (p/'reference-count-v2.stdout').read_text().splitlines()];assert len(counts)==4
for detail in details:
 selected=[r for r in counts if r['case']==detail['case']];assert len(selected)==2
 detail['inertia_counts']=selected;detail['window_supported']=all(r['lower_valid'] and r['upper_valid'] and r['window_count']==detail['reference_count'] for r in selected)
detail_note='Separate sparse MUMPS instances with two orderings plus original-problem residual and B-orthogonality checks support each reference window. MUMPS is also used by production, so this is not an independent algorithm or a full-spectrum oracle. Existing reference files and prior completeness labels are unchanged.'
result=dict(cases=details,note=detail_note,hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ['reference_count_v2.cpp','reference_count_v2.cpp.o','reference-count-v2']})
(p/'reference-window-results-v2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(cases=[dict(case=r['case'],window_supported=r['window_supported'],reference_count=r['reference_count'],max_eta=r['max_eta'],b_orthogonality=r['b_orthogonality']) for r in details],note=detail_note)),flush=True)
