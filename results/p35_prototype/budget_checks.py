import json,os,subprocess
from pathlib import Path
p=Path('/tmp/os2026-p35');old=Path('/tmp/os2026-p34')
groups=[(old/'fresh-data',['fresh-12-coupled-complex-hep','fresh-13-coupled-complex-hep','fresh-22-blocks-complex-ghep','fresh-31-coupled-complex-ghep'],[.06,.09,.13,.2],'small'),(p/'large-data',json.loads((p/'large-inputs.json').read_text()),[.15,.25,.4,.8],'large')]
for root,cases,budgets,group in groups:
 for budget in budgets:
  env=dict(os.environ,P35_MEMORY_BUDGET_GB=str(budget));tag=f'p35-budget-{group}-{str(budget).replace(".","p")}'
  subprocess.run(['python','-u',str(p/'compare.py'),'--solvers','hsolve-accepted,hsolve-packed,hsolve-acceptednative,hsolve-packednative','--reps','1','--timeout','60','--cores','8-15','--mem-gb','12','--root',str(root),'--tag',tag,'--out-dir',str(p)]+cases,env=env,check=True)
