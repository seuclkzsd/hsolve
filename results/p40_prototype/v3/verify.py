import json,sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
p=Path('/tmp/os2026-p40/v3');variant=sys.argv[1];items=json.loads((p/f'{variant}-manifest.json').read_text())
outputs={x['id']:x for x in map(json.loads,(p/f'{variant}-check.stdout').read_text().splitlines())};results=[]
for item in items:
 row=outputs[item['id']];assert row.get('valid',True),row
 if item.get('singular',False):assert not row['initial_valid'];continue
 a=sp.load_npz(item['a']).astype(np.clongdouble)*np.longdouble(item.get('alpha',1.))
 b=(sp.load_npz(item['b']).astype(np.clongdouble) if 'b' in item else sp.eye(a.shape[0],dtype=np.clongdouble))*np.longdouble(item.get('beta',0.))
 rhs=np.load(item['rhs']).astype(np.clongdouble)
 for name in row['solves']:
  x=np.load(name).astype(np.clongdouble);r=rhs[:,:x.shape[1]]
  eta=float(np.max(abs(a@x+b@x-r)/np.maximum(abs(a)@abs(x)+abs(b)@abs(x)+abs(r),np.finfo(float).tiny)))
  results.append(dict(id=item['id'],nrhs=x.shape[1],eta=eta,valid=bool(np.isfinite(eta) and eta<=1e-10)))
(p/f'{variant}-check-results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(x['valid'] for x in results),[x for x in results if not x['valid']]
print(json.dumps(dict(variant=variant,linear_checks=len(results),valid=sum(x['valid'] for x in results),max_eta=max(x['eta'] for x in results),singular_rejections=sum(x.get('singular',False) for x in items),lazy_fallback_inputs=sum(x.get('analyses',0)>1 for x in outputs.values()))),flush=True)
