import json,os,subprocess,time
from pathlib import Path

P=Path('/tmp/os2026-p39/recheck3');P.mkdir(exist_ok=True);REPO=Path('/tmp/os2026-p10-repair.9doyhO')
TARGET=set(range(16,32))|set(range(48,64));HZ=os.sysconf('SC_CLK_TCK')
AVAILABLE=set(os.sched_getaffinity(0))
os.sched_setaffinity(0,{0})

def snapshot():
    threads={};parents={};unreadable=0
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        pid=int(process.name)
        try:
            owner=process.stat().st_uid
            raw=(process/'stat').read_text();fields=raw[raw.rfind(')')+2:].split();parents[pid]=int(fields[1])
            for task in (process/'task').iterdir():
                try:
                    raw=(task/'stat').read_text();f=raw[raw.rfind(')')+2:].split()
                    threads[(pid,int(task.name),int(f[19]))]=(float(int(f[11])+int(f[12]))/HZ,int(f[36]),owner,raw[raw.find('(')+1:raw.rfind(')')])
                except (OSError,ValueError,IndexError):unreadable+=1
        except (OSError,ValueError,IndexError):unreadable+=1
    return dict(threads=threads,parents=parents,unreadable=unreadable)

def descendants(parents,root):
    found={os.getpid()}
    if root>0:found.add(root)
    while True:
        new={pid for pid,parent in parents.items() if parent in found}-found
        if not new:return found
        found.update(new)

def activity(a,b,elapsed,root=0):
    excluded=descendants(a['parents'],root)|descendants(b['parents'],root)
    events=[];target_cpu=0.;total_cpu=0.
    for key,row in b['threads'].items():
        if key[0] in excluded or key not in a['threads']:continue
        old=a['threads'][key];delta=max(0.,row[0]-old[0]);fraction=delta/elapsed
        overlap=row[1] in TARGET or old[1] in TARGET
        total_cpu+=fraction
        if overlap:target_cpu+=fraction
        if fraction>=.1:events.append(dict(pid=key[0],tid=key[1],uid=row[2],comm=row[3],cpu_s=delta,cpu_fraction=fraction,previous_cpu=old[1],current_cpu=row[1],target_overlap=overlap))
    return dict(target_cpu_fraction=target_cpu,total_external_cpu_fraction=total_cpu,
                busy=target_cpu>=.8 or total_cpu>=2.,events=events,unreadable=b['unreadable'])

# Qualification is fixed before this batch: >=0.8 CPU on the target/sibling
# set or >=2 CPUs anywhere, excluding this monitor and guarded descendants.
# Last-CPU samples cannot locate all work of a migrating/short-lived thread.
started=time.monotonic();idle=0;previous=snapshot();previous_time=time.monotonic()
samples=[]
with (P/'screen-monitor.jsonl').open('w') as out:
    while idle<60:
        time.sleep(1);current=snapshot();now=time.monotonic();row=activity(previous,current,now-previous_time)
        idle=0 if row['busy'] else idle+1
        out.write(json.dumps(dict(phase='idle',begin=previous_time,end=now,stable_seconds=idle,**row))+'\n');out.flush()
        previous,previous_time=current,now
        if now-started>180:
            result=dict(returncode=75,performance_usable=False,benchmark_started=False,elapsed_s=now-started,reason='No 60-second stable idle window within 180 seconds',criterion='Reject >=0.8 target CPU or >=2 external CPUs globally; require 60 idle samples before launch.')
            (P/'screen-monitor-result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result),flush=True)
            raise SystemExit(75)
    cmd=['env/run.sh','python','tools/run/guard.py','--exclusive','--cores','16-31','--mem-gb','32','--timeout','900','--summary',str(P/'screen-guard.json'),'--','bash','/tmp/os2026-p39/recheck3_screen.sh']
    print('Starting P39 guarded comparison after 60-second stable idle window',flush=True)
    with (P/'screen.log').open('w') as log:
        child=subprocess.Popen(cmd,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,
                               preexec_fn=lambda:os.sched_setaffinity(0,AVAILABLE))
        while child.poll() is None:
            time.sleep(.5);current=snapshot();now=time.monotonic();row=activity(previous,current,now-previous_time,child.pid)
            sample=dict(phase='run',begin=previous_time,end=now,**row);samples.append(sample)
            out.write(json.dumps(sample)+'\n');out.flush();previous,previous_time=current,now
    bad=[x for x in samples if x['busy']]
    rows=[json.loads(x) for x in (P.parent/'runs.jsonl').read_text().splitlines() if '/p39-recheck3/' in json.loads(x)['out']]
    qualification=[]
    for row in rows:
        hits=[x for x in bad if x['end']>=row['started_monotonic'] and x['begin']<=row['ended_monotonic']]
        qualification.append(dict(case=row['case'],solver=row['solver'],out=row['out'],valid=row.get('valid',False),busy_intervals=len(hits),performance_usable=bool(row.get('valid')) and not hits))
    result=dict(returncode=child.returncode,elapsed_s=time.monotonic()-started,busy_intervals=len(bad),
                performance_usable=child.returncode==0 and not bad and len(rows)==40 and all(x.get('valid') for x in rows),
                rows=qualification,
                criterion='Per-thread CPU deltas; previous or current CPU in 16-31/48-63 counts as target overlap. Reject >=0.8 target CPU or >=2 external CPUs globally. Monitor pinned to CPU0; guarded descendants excluded.',
                caveat='Periodic /proc sampling cannot prove exclusive ownership or attribute every migrating/short-lived thread; all samples retained. P31 affinity-only results are not reclassified.')
    (P/'screen-monitor-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
    raise SystemExit(child.returncode)
