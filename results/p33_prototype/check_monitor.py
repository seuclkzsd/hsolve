import ast,os
from pathlib import Path
src=ast.parse(Path('/tmp/os2026-p33/monitored_screen.py').read_text())
fn=next(x for x in src.body if isinstance(x,ast.FunctionDef) and x.name=='descendants')
ns={'os':os};exec(compile(ast.Module(body=[fn],type_ignores=[]),'monitor-descendants','exec'),ns)
me=os.getpid();parents={1:0,101:1,102:101,me:1,me+100000:me}
f=ns['descendants'];assert f(parents,0)=={me,me+100000};assert f(parents,101)=={me,me+100000,101,102}
assert 1 not in f(parents,0) and 101 not in f(parents,0)
print('Monitor exclusion regression passed: idle excludes only monitor descendants; run also excludes guarded descendants.')
