import hashlib
import json
import tarfile
from pathlib import Path

p = Path('/tmp/os2026-p38-local')
meta = json.loads((p/'archive-result.json').read_text())
archive = Path('/tmp/os2026-p38-results.tar')
assert archive.stat().st_size == meta['size']
h = hashlib.sha256()
with archive.open('rb') as f:
    for block in iter(lambda: f.read(1 << 20), b''):
        h.update(block)
assert h.hexdigest() == meta['sha256']
with tarfile.open(archive) as t:
    members = t.getmembers()
    assert len(members) == meta['members']
    manifest = json.load(t.extractfile('MANIFEST.json'))
    assert len(manifest) == meta['content_members']
    assert {m.name for m in members} == set(manifest) | {'MANIFEST.json'}
    for name,r in manifest.items():
        member = t.getmember(name)
        assert member.isfile() and member.size == r['size'], name
        h = hashlib.sha256()
        with t.extractfile(member) as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                h.update(block)
        assert h.hexdigest() == r['sha256'], name
    for name,dest in [('experiment/collected.json','collected.json'),('experiment/runs.jsonl','runs-final.jsonl')]:
        (p/dest).write_bytes(t.extractfile(name).read())
result = dict(verified=True, **meta)
(p/'archive-verified.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
