import decimal,json
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p40/v3')
items=json.loads((p/'enclosed-manifest.json').read_text())
outputs={x['id']:x for x in map(json.loads,(p/'enclosed-check.stdout').read_text().splitlines())}
def loaded(path):
 a=sp.load_npz(path).astype(np.complex128).tocsr();a.sum_duplicates();a.sort_indices()
 if bool(sp.triu(a,k=1).nnz)!=bool(sp.tril(a,k=-1).nnz):a=a+a.getH()-sp.diags(a.diagonal())
 if (a-a.getH()).nnz:a=(a*.5+a.getH()*.5).tocsr()
 a.sort_indices();return a
decimal.getcontext().prec=90
D=lambda x:decimal.Decimal.from_float(float(x))
results=[];precise=[]
for item in items:
 row=outputs[item['id']]
 if item.get('singular'):continue
 a=loaded(item['a']);b=loaded(item['b']) if 'b' in item else None
 alpha=item.get('alpha',1.);beta=item.get('beta',0.)
 rhs=np.load(item['rhs']);aa=a.astype(np.clongdouble)*np.longdouble(alpha)
 bb=(b.astype(np.clongdouble) if b is not None else sp.eye(a.shape[0],dtype=np.clongdouble))*np.longdouble(beta)
 abs1=lambda x:np.abs(x.real)+np.abs(x.imag)
 absa=aa.copy();absa.data=abs1(aa.data);absb=bb.copy();absb.data=abs1(bb.data)
 entries=int(max(np.diff(a.indptr)))+(int(max(np.diff(b.indptr))) if b is not None else 1)
 for record in row['residuals']:
  x=np.load(record['solution']);r=np.load(record['enclosure']);nrhs=x.shape[1]
  oracle=rhs[:,:nrhs].astype(np.clongdouble)-(aa@x+bb@x)
  den=abs1(rhs[:,:nrhs])+absa@abs1(x)+absb@abs1(x)
  eta=abs1(oracle)/np.maximum(den,np.finfo(np.longdouble).tiny)
  worst=np.unravel_index(int(np.argmax(eta)),eta.shape)
  uncertainty=den*(32*(entries+4)*np.finfo(np.longdouble).eps)
  if record['enclosed']:
   radius=np.load(record['bound']);assert np.all(np.isfinite(radius)) and np.all(radius.real>=0) and np.all(radius.imag>=0)
   assert np.all(abs(oracle.real-r.real)<=radius.real+uncertainty),(item['id'],nrhs,'real enclosure')
   assert np.all(abs(oracle.imag-r.imag)<=radius.imag+uncertainty),(item['id'],nrhs,'imag enclosure')
   assert float(np.max(eta))<=record['eta_upper']+float(64*(entries+4)*np.finfo(np.longdouble).eps)
  results.append(dict(id=item['id'],nrhs=nrhs,enclosed=record['enclosed'],eta_upper=record['eta_upper'],reference_eta=float(np.max(eta)),valid=True))
  if not record['enclosed']:continue
  indices={(i,j) for i in [0,x.shape[0]//2,x.shape[0]-1] for j in [0,nrhs-1]};indices.add(worst)
  for i,j in sorted(indices):
   dr,di=D(rhs[i,j].real),D(rhs[i,j].imag);denom=abs(dr)+abs(di)
   def add(k,z,scale):
    global dr,di,denom
    ar,ai=D(scale)*D(z.real),D(scale)*D(z.imag);xr,xi=D(x[k,j].real),D(x[k,j].imag)
    dr-=ar*xr-ai*xi;di-=ar*xi+ai*xr;denom+=(abs(ar)+abs(ai))*(abs(xr)+abs(xi))
   for q in range(a.indptr[i],a.indptr[i+1]):add(a.indices[q],a.data[q],alpha)
   if b is not None:
    for q in range(b.indptr[i],b.indptr[i+1]):add(b.indices[q],b.data[q],beta)
   else:add(i,1.+0j,beta)
   errr=abs(D(r[i,j].real)-dr);erri=abs(D(r[i,j].imag)-di)
   oracle_round=decimal.Decimal('1e-75')*denom
   valid=errr<=D(radius[i,j].real)+oracle_round and erri<=D(radius[i,j].imag)+oracle_round
   actual=(abs(dr)+abs(di))/max(denom,decimal.Decimal('1e-4900'))
   valid=valid and actual<=D(record['eta_upper'])+decimal.Decimal('1e-75')
   precise.append(dict(id=item['id'],nrhs=nrhs,row=int(i),column=int(j),real_error=str(errr),imag_error=str(erri),real_bound=float(radius[i,j].real),imag_bound=float(radius[i,j].imag),reference_eta=str(actual),reported_eta_upper=record['eta_upper'],valid=bool(valid)))
(p/'enclosure-array-results.json').write_text(json.dumps(results,indent=2)+'\n')
(p/'enclosure-decimal-results.json').write_text(json.dumps(precise,indent=2)+'\n')
assert len(results)==1540 and all(r['valid'] for r in results)
assert precise and all(r['valid'] for r in precise),[r for r in precise if not r['valid']][:8]
summary=dict(checks=len(results),enclosed=sum(r['enclosed'] for r in results),decimal_checks=len(precise),decimal_valid=sum(r['valid'] for r in precise),qualified=True)
(p/'enclosure-qualified.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
