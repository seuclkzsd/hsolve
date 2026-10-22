import json
from pathlib import Path
import numpy as np
p=Path('/tmp/os2026-p36');rows=json.loads((p/'control-manifest.json').read_text());results=[]
for item in rows:
 if item.get('singular'):continue
 for nrhs in [1,3,4,5,8]:
  a=np.load(p/'check-control'/(item['id']+'-result-'+str(nrhs)+'.npy'))
  b=np.load(p/'check-fused'/(item['id']+'-result-'+str(nrhs)+'.npy'))
  results.append(dict(id=item['id'],nrhs=nrhs,identical=bool(np.array_equal(a,b))))
(p/'fused-equivalence.json').write_text(json.dumps(results,indent=2)+'\n')
summary=dict(checks=len(results),identical=sum(r['identical'] for r in results))
print(json.dumps(summary),flush=True)
assert all(r['identical'] for r in results),[r for r in results if not r['identical']]
