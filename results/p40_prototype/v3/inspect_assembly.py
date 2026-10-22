import hashlib,json,re,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p40/v3');results=[]
for name in ['enclosed-objects/solver.cpp.o','check-enclosed.cpp.o','boundary_check_v2.cpp.o']:
 obj=p/name;text=subprocess.run(['objdump','-d','-C',str(obj)],check=True,capture_output=True,text=True).stdout
 functions={};active=None
 for line in text.splitlines():
  match=re.match(r'^[0-9a-f]+ <(.+)>:$',line)
  if match:
   active=match[1] if 'Backend::enclosed_residual' in match[1] else None
   if active:functions.setdefault(active,[])
  elif active:functions[active].append(line)
 body='\n'.join('\n'.join([name]+lines) for name,lines in functions.items())
 path=p/(obj.name+'.enclosure-assembly.txt');path.write_text(body+'\n')
 implicit=[line for line in body.splitlines() if re.search(r'\bvf(?:n?madd)\w*pd\b',line) and '%zmm' in line]
 products=[line for line in body.splitlines() if re.search(r'\bvfmsub\w*pd\b',line) and '%zmm' in line]
 result=dict(object=name,sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),functions=len(functions),explicit_product_error_instructions=len(products),implicit_vector_fma=implicit,qualified=bool(functions and products and not implicit))
 results.append(result)
(p/'assembly-check-results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['qualified'] for r in results),results
print(json.dumps(results),flush=True)
