import json,re
from pathlib import Path
p=Path('/tmp/os2026-p36');rows=[json.loads(s) for s in (p/'runs.jsonl').read_text().splitlines()]
selected=[r for r in rows if r['solver']=='hsolve-reuse' and '/p36-reuse-' in r['out']]
assert len(selected)==80 and all(r['valid'] for r in selected)
results=[]
for row in selected:
 root=Path(row['out']);log=root.parent/('guard-'+root.name+'.stderr.txt')
 probes=[dict(accepted=int(a),reused=int(b)) for a,b in re.findall(r'P36 requested_probe accepted=(\d).*? reused=(\d)',log.read_text())]
 old=next((r for r in rows if r['case']==row['case'] and r['solver']=='hsolve-simd' and '/p36-screen/' not in r['out']),None)
 record=dict(case=row['case'],out=row['out'],probes=probes,factorizations=row.get('phases',{}).get('factorizations'),rhs=row.get('phases',{}).get('solves'))
 if old:record.update(simd_factorizations=old.get('phases',{}).get('factorizations'),simd_rhs=old.get('phases',{}).get('solves'))
 results.append(record)
accepted=sum(r['reused'] and r['accepted'] for x in results for r in x['probes'])
rejected=sum(r['reused'] and not r['accepted'] for x in results for r in x['probes'])
assert accepted>0 and rejected>0,(accepted,rejected)
(p/'reuse-probe-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(dict(valid=len(selected),reused_accepted_probes=accepted,reused_rejected_probes=rejected)),flush=True)
