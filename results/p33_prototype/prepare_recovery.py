from pathlib import Path
import shutil
p=Path('/tmp/os2026-p33');q=p/'recovery-only';q.mkdir(exist_ok=True)
shutil.copy2(p/'initial-failed/band_backend.hpp',q/'band_backend.hpp')
for name in ['band_ldlh.cpp','check.cpp','steps.cpp']:shutil.copy2(p/name,q/name)
(q/'solver.cpp').write_text((p/'solver.cpp').read_text().replace('/tmp/os2026-p33/band_backend.hpp','/tmp/os2026-p33/recovery-only/band_backend.hpp'))
(q/'build.py').write_text((p/'build.py').read_text().replace("p=Path('/tmp/os2026-p33')","p=Path('/tmp/os2026-p33/recovery-only')"))
