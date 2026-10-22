import decimal,json
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p37')
items=json.loads((p/'dd-manifest.json').read_text())
outputs={x['id']:x for x in map(json.loads,(p/'dd-check.stdout').read_text().splitlines())}
# Kernel inputs are the matrices produced by load_matrix, whose documented
# Hermitian normalization precedes construction of ShiftedPencil. The separate
# linear-solve verifier continues to check the unmodified input files.
def loaded_matrix(path):
 a=sp.load_npz(path).astype(np.complex128).tocsr();a.sum_duplicates();a.sort_indices()
 upper=sp.triu(a,k=1).nnz;lower=sp.tril(a,k=-1).nnz
 if bool(upper)!=bool(lower):
  a=a+a.getH()-sp.diags(a.diagonal())
 if (a-a.getH()).nnz:
  a=(a*0.5+a.getH()*0.5).tocsr()
 a.sort_indices();return a

results=[];precise=[];decimal.getcontext().prec=90
D=lambda x:decimal.Decimal.from_float(float(x))
for number,item in enumerate(items):
 row=outputs[item['id']]
 if item.get('singular'):continue
 a0=loaded_matrix(item['a']);b0=loaded_matrix(item['b']) if 'b' in item else None
 alpha=item.get('alpha',1.);beta=item.get('beta',0.)
 a=a0.astype(np.clongdouble)*np.longdouble(alpha)
 b=(b0.astype(np.clongdouble) if b0 is not None else sp.eye(a.shape[0],dtype=np.clongdouble))*np.longdouble(beta)
 rhs=np.load(item['rhs']).astype(np.clongdouble)
 for record in row['residuals']:
  x=np.load(record['solution']).astype(np.clongdouble);r=np.load(record['residual']).astype(np.clongdouble);nrhs=x.shape[1]
  oracle=rhs[:,:nrhs]-(a@x+b@x)
  denom=abs(a)@abs(x)+abs(b)@abs(x)+abs(rhs[:,:nrhs])
  ratio=float(np.max(abs(r-oracle)/np.maximum(denom,np.finfo(float).tiny)))
  result=dict(id=item['id'],nrhs=nrhs,vectorized=record['vectorized'],residual_difference_ratio=ratio,valid=bool(np.isfinite(ratio) and ratio<=1e-16))
  results.append(result)
  if not record['vectorized'] or number%13!=0:continue
  for i in sorted({0,x.shape[0]//2,x.shape[0]-1}):
   for col in sorted({0,nrhs-1}):
    br,bi=D(rhs[i,col].real),D(rhs[i,col].imag);dr,di=br,bi;den=abs(br)+abs(bi)
    def add(k,z,scale):
     global dr,di,den
     ar,ai=D(scale)*D(z.real),D(scale)*D(z.imag);xr,xi=D(x[k,col].real),D(x[k,col].imag)
     dr-=ar*xr-ai*xi;di-=ar*xi+ai*xr;den+=(abs(ar)+abs(ai))*(abs(xr)+abs(xi))
    for q in range(a0.indptr[i],a0.indptr[i+1]):add(a0.indices[q],a0.data[q],alpha)
    if b0 is not None:
     for q in range(b0.indptr[i],b0.indptr[i+1]):add(b0.indices[q],b0.data[q],beta)
    else:add(i,1.+0j,beta)
    err=abs(D(r[i,col].real)-dr)+abs(D(r[i,col].imag)-di)
    bound=decimal.Decimal('2e-27')*den+decimal.Decimal('4e-16')*(abs(dr)+abs(di))
    precise.append(dict(id=item['id'],nrhs=nrhs,row=i,column=col,error=str(err),bound=str(bound),valid=err<=bound))
(p/'residual-check-results-v2.json').write_text(json.dumps(results,indent=2)+'\n')
(p/'decimal-check-results-v2.json').write_text(json.dumps(precise,indent=2)+'\n')
assert len(results)==1540 and all(r['valid'] for r in results),[r for r in results if not r['valid']][:8]
assert precise and all(r['valid'] for r in precise),[r for r in precise if not r['valid']][:8]
assert any(r['vectorized'] for r in results)
print(json.dumps(dict(checks=len(results),vectorized=sum(r['vectorized'] for r in results),max_ratio=max(r['residual_difference_ratio'] for r in results),decimal_checks=len(precise),decimal_valid=sum(r['valid'] for r in precise))),flush=True)
