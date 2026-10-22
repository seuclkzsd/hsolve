import json,sys
from pathlib import Path
import numpy as np
from scipy import sparse
sys.path.insert(0,'/tmp/os2026-p10-repair.9doyhO')
from tools import case as cio
from tools.eval import common
common.require_guard('P38 sparse translation inspection')
p=Path('/tmp/os2026-p38');data=Path('/share/home/linzihan/os2026/data');rows=[]
for name in ['yee-photonic-rods-1e4','yee-photonic-spheres-1e4','yee-bloch-1e4','syn-zero-cluster-complex-1e4']:
 c=cio.load_case(name,root=data);a=c.A.tocsr();n=a.shape[0];attempts=[]
 for period in range(3,65):
  if n%period:continue
  first=a[0,1];last=a[0,period-1]
  if first==0 or last==0:continue
  wrap=np.conj(last/first)
  if abs(abs(wrap)-1)>128*np.finfo(float).eps:continue
  wrap/=abs(wrap);results=[]
  for mat in [a]+([] if c.B is None else [c.B.tocsr()]):
   rr=[];cc=[];vv=[]
   for g in range(n//period):
    start,end=mat.indptr[g*period:g*period+2]
    cols=mat.indices[start:end];values=mat.data[start:end]
    for t in range(period):
     target=cols//period*period+(cols%period+t)%period
     factor=np.where(cols%period+t>=period,wrap,1.)
     rr.extend([g*period+t]*len(cols));cc.extend(target);vv.extend(values*factor)
   rebuilt=sparse.coo_matrix((vv,(rr,cc)),shape=(n,n)).tocsr()
   diff=rebuilt-mat;norm=np.max(np.asarray(abs(mat).sum(axis=1)))
   error=float(np.max(np.asarray(abs(diff).sum(axis=1))));results.append(dict(absolute_infinity_error=error,relative_infinity_error=error/norm,nnz=mat.nnz,reconstructed_nnz=rebuilt.nnz))
  attempts.append(dict(period=period,block_order=n//period,phase=float(np.angle(wrap)),matrices=results,recognized=all(r['relative_infinity_error']<=128*np.finfo(float).eps for r in results)))
 rows.append(dict(case=name,n=n,attempts=attempts));print(json.dumps(rows[-1]),flush=True)
(p/'structure-results.json').write_text(json.dumps(rows,indent=2)+'\n')
