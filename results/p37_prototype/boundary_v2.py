import decimal,json
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p37')
selected=json.loads((p/'boundary-manifest.json').read_text())
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
 # The API returns complex<double>, even when its accumulator is extended.
 # Account separately for the unavoidable final real/imaginary rounding.
 roundoff=(np.abs(np.spacing(r.real.astype(float))).astype(np.longdouble)+np.abs(np.spacing(r.imag.astype(float))).astype(np.longdouble))*np.longdouble(.5)
 error=np.abs(r-oracle)
 entries=int(max(np.diff(a.indptr)))+int(max(np.diff(b.tocsr().indptr)))
 reference_bound=den*(16*max(1,entries)*np.finfo(np.longdouble).eps)
 adjusted=float(np.max(np.maximum(0,error-roundoff)/np.maximum(den,np.finfo(np.longdouble).tiny)))
 row['ratio']=ratio;row['rounding_adjusted_ratio']=adjusted;row['valid']=bool(np.all(np.isfinite(error)) and np.all(error<=roundoff+reference_bound))
(p/'boundary-results-v2.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(r['valid'] for r in rows),[r for r in rows if not r['valid']]
summary=dict(checks=len(rows),valid=sum(r['valid'] for r in rows),vectorized=sum(r['vectorized'] for r in rows),fallback=sum(not r['vectorized'] for r in rows),nonfinite=sum(r['nonfinite'] for r in rows),max_ratio=max(r.get('ratio',0.) for r in rows),max_rounding_adjusted_ratio=max(r.get('rounding_adjusted_ratio',0.) for r in rows))
decimal.getcontext().prec=90
D=lambda x:decimal.Decimal.from_float(float(x))
precise=[]
for row in rows:
 if row['nonfinite']:continue
 a,b=matrices[row['id']];prefix=row['prefix'];x=np.load(prefix+'-x.npy');rhs=np.load(prefix+'-rhs.npy');r=np.load(prefix+'-r.npy')
 for i in sorted({0,x.shape[0]//2,x.shape[0]-1}):
  for col in sorted({0,x.shape[1]-1}):
   dr,di=D(rhs[i,col].real),D(rhs[i,col].imag);den=abs(dr)+abs(di)
   def add(k,z,scale):
    global dr,di,den
    ar,ai=D(scale)*D(z.real),D(scale)*D(z.imag);xr,xi=D(x[k,col].real),D(x[k,col].imag)
    dr-=ar*xr-ai*xi;di-=ar*xi+ai*xr;den+=(abs(ar)+abs(ai))*(abs(xr)+abs(xi))
   for q in range(a.indptr[i],a.indptr[i+1]):add(a.indices[q],a.data[q],row['alpha'])
   if b is not None:
    for q in range(b.indptr[i],b.indptr[i+1]):add(b.indices[q],b.data[q],row['beta'])
   else:add(i,1.+0j,row['beta'])
   err=abs(D(r[i,col].real)-dr)+abs(D(r[i,col].imag)-di)
   accumulator=decimal.Decimal('2e-27' if row['vectorized'] else '2e-17')
   bound=accumulator*den+decimal.Decimal('4e-16')*(abs(dr)+abs(di))
   precise.append(dict(id=row['id'],profile=row['profile'],nrhs=row['nrhs'],row=i,column=col,error=str(err),bound=str(bound),valid=err<=bound))
(p/'boundary-decimal-results.json').write_text(json.dumps(precise,indent=2)+'\n')
assert precise and all(r['valid'] for r in precise),[r for r in precise if not r['valid']][:8]
summary.update(decimal_checks=len(precise),decimal_valid=sum(r['valid'] for r in precise))
(p/'boundary-qualified-v2.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
