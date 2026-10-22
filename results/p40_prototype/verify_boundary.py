import decimal,json
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p40');decimal.getcontext().prec=90
D=lambda x:decimal.Decimal.from_float(float(x))
def loaded(path):
 a=sp.load_npz(path).astype(np.complex128).tocsr();a.sum_duplicates();a.sort_indices()
 if bool(sp.triu(a,k=1).nnz)!=bool(sp.tril(a,k=-1).nnz):a=a+a.getH()-sp.diags(a.diagonal())
 if (a-a.getH()).nnz:a=(a*.5+a.getH()*.5).tocsr()
 return a
items=json.loads((p/'boundary-manifest.json').read_text())
matrices={r['id']:(loaded(r['a']),loaded(r['b']) if 'b' in r else None) for r in items}
rows=[json.loads(s) for s in (p/'boundary-check.stdout').read_text().splitlines()]
assert len(rows)==560 and all(r['valid'] for r in rows)
checks=[]
for row in rows:
 if not row['vectorized']:continue
 a,b=matrices[row['id']];prefix=row['prefix']
 x=np.load(prefix+'-x.npy');rhs=np.load(prefix+'-rhs.npy');r=np.load(prefix+'-r.npy');bound=np.load(prefix+'-bound.npy')
 assert np.all(np.isfinite(bound)) and np.all(bound.real>=0) and np.all(bound.imag>=0)
 xd=[[(D(z.real),D(z.imag)) for z in xr] for xr in x]
 maximum=decimal.Decimal(0);largest_ratio=decimal.Decimal(0);count=0;valid=True
 for i in range(a.shape[0]):
  terms=[]
  for q in range(a.indptr[i],a.indptr[i+1]):terms.append((a.indices[q],D(row['alpha'])*D(a.data[q].real),D(row['alpha'])*D(a.data[q].imag)))
  if b is not None:
   for q in range(b.indptr[i],b.indptr[i+1]):terms.append((b.indices[q],D(row['beta'])*D(b.data[q].real),D(row['beta'])*D(b.data[q].imag)))
  else:terms.append((i,D(row['beta']),decimal.Decimal(0)))
  for j in range(x.shape[1]):
   dr,di=D(rhs[i,j].real),D(rhs[i,j].imag);den=abs(dr)+abs(di)
   for k,ar,ai in terms:
    xr,xi=xd[k][j];dr-=ar*xr-ai*xi;di-=ar*xi+ai*xr;den+=(abs(ar)+abs(ai))*(abs(xr)+abs(xi))
   errr,erri=abs(D(r[i,j].real)-dr),abs(D(r[i,j].imag)-di)
   br,bi=D(bound[i,j].real),D(bound[i,j].imag);oracle_round=decimal.Decimal('1e-75')*den
   valid=valid and errr<=br+oracle_round and erri<=bi+oracle_round
   largest_ratio=max(largest_ratio,errr/max(br,decimal.Decimal('1e-4900')),erri/max(bi,decimal.Decimal('1e-4900')))
   maximum=max(maximum,(abs(dr)+abs(di))/max(den,decimal.Decimal('1e-4900')));count+=2
 valid=valid and maximum<=D(row['eta'])+decimal.Decimal('1e-75')
 if row['eta']<=1e-12:valid=valid and maximum<=D(1e-12)
 if row['profile'] in ['threshold_half','threshold_below']:valid=valid and maximum<D(1e-12) and row['eta']<=1e-12
 if row['profile'] in ['threshold_above','threshold_twice']:valid=valid and maximum>D(1e-12) and row['eta']>1e-12
 checks.append(dict(id=row['id'],profile=row['profile'],nrhs=row['nrhs'],decimal_components=count,reference_eta=str(maximum),eta_upper=row['eta'],accepted_by_bound=row['eta']<=1e-12,max_error_over_radius=float(largest_ratio),valid=bool(valid)))
(p/'boundary-decimal-results.json').write_text(json.dumps(checks,indent=2)+'\n')
assert checks and all(r['valid'] for r in checks),[r for r in checks if not r['valid']][:8]
result=dict(checks=len(rows),enclosed=sum(r['vectorized'] for r in rows),fallback=sum(not r['vectorized'] for r in rows),nonfinite=sum(r['nonfinite'] for r in rows),decimal_records=len(checks),decimal_components=sum(r['decimal_components'] for r in checks),threshold_checks=sum(r['profile'].startswith('threshold_') for r in checks),max_error_over_radius=max(r['max_error_over_radius'] for r in checks),qualified=True)
(p/'boundary-qualified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
