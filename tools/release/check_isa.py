#!/usr/bin/env python3
"""Check that an hsolve build is portable: no AVX / AVX2 / AVX-512 / FMA instruction outside the
kernels that are only called after a CPUID check.

The release preset compiles for the x86-64 baseline (CMakePresets.json; HSOLVE_NATIVE=OFF). The SIMD
kernels carry their wider variants as function target attributes and select one at run time:
src/sparse/kernels.cpp (AVX-512F, __builtin_cpu_supports) and src/blas (AVX-512F or AVX2+FMA,
route.cpp). This tool disassembles the object files of hsolve's own targets (objdump) and lists every
function that uses a VEX / EVEX encoded instruction; such a function must belong to one of those
source files and to a code path behind their CPUID dispatch, i.e. it must match ALLOWED. Third-party
libraries (OpenBLAS, MUMPS) are not checked here: OpenBLAS selects its kernels at run time and the
default MUMPS is built for nocona (tools/dev/mumps_cache.sh).

    python3 tools/release/check_isa.py build/release        exit 1 if a function outside ALLOWED needs AVX
    python3 tools/release/check_isa.py build/native --list  list every function with wide instructions
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Objects of hsolve's own targets (libhsolve, the BLAS hook, the GPU offload, the command line).
TARGET_DIRS = ("hsolve.dir", "hsolve_blas.dir", "hsolve_gpu.dir", "hsolve_cli_main.dir", "hsolve_cli.dir",
               "hsolve_blashook.dir")
# Source file -> demangled function names (regular expressions) that may use AVX-class instructions:
# the target-attributed kernels and what they inline, reached only after the CPUID check.
ALLOWED = {
    "src/sparse/kernels.cpp": [r"_avx512<"],                       # spmm_rows_avx512, residual_rows_avx512
    "src/blas/narrow_kernels.cpp": [r"::avx2::", r"::avx512::"],   # namespaces of the dispatched kernels
}
WIDE = re.compile(r"%[yz]mm\d+|%k[0-7]\b")
FUNC = re.compile(r"^[0-9a-f]+ <(.+)>:$")


def wide_functions(obj: Path) -> list[tuple[str, str]]:
    """(function, first wide instruction) for every function of obj with a VEX/EVEX instruction."""
    out = subprocess.run([os.environ.get("OBJDUMP") or "objdump", "-d", "-C", "--no-show-raw-insn", str(obj)], check=True,
                         capture_output=True, text=True).stdout
    found: dict[str, str] = {}
    func = None
    for line in out.splitlines():
        m = FUNC.match(line)
        if m:
            func = m.group(1)
            continue
        if func is None or func in found or "\t" not in line:
            continue
        insn = line.split("\t", 1)[1].strip()
        mnemonic = insn.split(None, 1)[0] if insn else ""
        # VEX/EVEX encodings: 'v'-prefixed SSE/AVX mnemonics, ymm/zmm/mask registers. ('verr' and
        # 'verw' are legacy segment instructions.)
        if (mnemonic.startswith("v") and mnemonic not in ("verr", "verw")) or WIDE.search(insn):
            found[func] = insn
    return sorted(found.items())


def source_of(obj: Path, build: Path) -> str:
    """CMake object path .../CMakeFiles/<target>.dir/<src path>.o -> <src path>."""
    rel = obj.relative_to(build).as_posix()
    m = re.search(r"CMakeFiles/[^/]+\.dir/(.+)\.o$", rel)
    return m.group(1) if m else rel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("build", type=Path, help="CMake build directory")
    ap.add_argument("--list", action="store_true", help="list every function with wide instructions")
    ns = ap.parse_args(argv)
    objs = sorted(p for d in TARGET_DIRS for p in (ns.build / "CMakeFiles" / d).rglob("*.o"))
    if not objs:
        print(f"check_isa: no object files of {TARGET_DIRS} under {ns.build}/CMakeFiles", file=sys.stderr)
        return 2
    bad = allowed = 0
    for obj in objs:
        src = source_of(obj, ns.build)
        for func, insn in wide_functions(obj):
            ok = any(re.search(p, func) for p in ALLOWED.get(src, []))
            allowed += ok
            bad += not ok
            if ns.list or not ok:
                print(f"{'dispatched' if ok else 'NOT PORTABLE'}  {src}: {func}  [{insn}]")
    print(f"check_isa: {len(objs)} object files, {allowed} dispatched SIMD function(s), "
          f"{bad} function(s) needing AVX outside a CPUID dispatch")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
