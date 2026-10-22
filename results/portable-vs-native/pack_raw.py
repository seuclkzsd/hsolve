#!/usr/bin/env python3
"""Pack an ab_cases.py run directory as a reproducible raw-data archive for the repository.

    pack_raw.py RUN_DIR OUT.tar.gz

Everything tools/bench/ab_cases.py table and tools/eval need to re-read is kept (runs.jsonl, guard
summaries, stderr, report.json, eigenvalues.npy, evaluation.json, eval.md); eigenvectors are left
out (size). The home directory in paths becomes "$HOME"; members are sorted, owned by 0:0, with a
fixed time stamp, gzip without one - the same run directory always gives the same bytes.
"""
from __future__ import annotations

import gzip
import io
import os
import sys
import tarfile
from pathlib import Path

SKIP = {"eigenvectors.npy"}
MTIME = 1792627200  # 2026-10-22, any fixed value


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    run_dir, out = Path(argv[0]).resolve(), Path(argv[1])
    homes = sorted({os.path.expanduser("~").encode(), os.path.realpath(os.path.expanduser("~")).encode()},
                   key=len, reverse=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in [run_dir] + sorted(run_dir.rglob("*")):
            if p.name in SKIP:
                continue
            info = tarfile.TarInfo(str(Path(run_dir.name) / p.relative_to(run_dir)) if p != run_dir else run_dir.name)
            info.uid = info.gid = 0
            info.mtime = MTIME
            if p.is_dir():
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(info)
            else:
                data = p.read_bytes()
                if p.suffix in (".json", ".jsonl", ".md", ".txt"):
                    for home in homes:
                        data = data.replace(home, b"$HOME")
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
    with open(out, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
        gz.write(buf.getvalue())
    print(f"{out}: {out.stat().st_size / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
