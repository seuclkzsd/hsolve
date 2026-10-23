# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 seuclkzsd and the hsolve contributors
"""tools/dev/spdx.py: every source file carries its SPDX header, and --fix places it correctly."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("spdx", ROOT / "tools" / "dev" / "spdx.py")
spdx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spdx)


def test_every_source_file_has_its_header():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "dev" / "spdx.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_adapted_openblas_kernels_name_both_licences():
    for path in spdx.MIXED:
        assert (ROOT / path).read_text().splitlines()[0] == \
            "// SPDX-License-Identifier: Apache-2.0 AND BSD-3-Clause"


def test_fix_keeps_shebang_encoding_and_docker_directives_first(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    files = {
        "tools/a.py": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"Doc.\"\"\"\n",
        "src/b.cpp": "int f() { return 1; }",
        "Dockerfile": "# syntax=docker/dockerfile:1\nFROM scratch\n",
        "results/c.py": "x = 1\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    assert spdx.main(["--fix", "--root", str(tmp_path)]) == 0
    assert spdx.main(["--fix", "--root", str(tmp_path)]) == 0  # idempotent
    a = (tmp_path / "tools/a.py").read_text().splitlines()
    assert a[:2] == ["#!/usr/bin/env python3", "# -*- coding: utf-8 -*-"]
    assert a[2] == "# SPDX-License-Identifier: Apache-2.0" and a[4] == '"""Doc."""'
    assert (tmp_path / "src/b.cpp").read_text().splitlines()[2] == "int f() { return 1; }"
    d = (tmp_path / "Dockerfile").read_text().splitlines()
    assert d[0] == "# syntax=docker/dockerfile:1" and d[1].startswith("# SPDX-License-Identifier")
    assert (tmp_path / "results/c.py").read_text() == "x = 1\n"  # records are not covered
