# hsolve 二进制包（Linux x86-64）

hsolve：大规模稀疏厄密（含不定、广义、B 不定）特征值问题的移位-求逆求解器，带精确的 Sylvester 惯性完备性证书。
项目主页：https://github.com/seuclkzsd/hsolve

本目录可放在任意位置使用，不需要 conda、编译器或 root 权限。运行要求：x86-64 CPU（任意型号，SIMD 内核运行时按
CPUID 选择）、glibc ≥ 2.17 的 Linux（CentOS 7 及之后的发行版），版本与构建信息见 `BUILD-INFO.txt`。

## 快速开始

```bash
bin/hsolve --A examples/cases/waveguide-50ghz/A.npz --B examples/cases/waveguide-50ghz/B.npz \
           --config examples/cases/waveguide-50ghz/config.json --out /tmp/wg
scripts/demo.sh --quick        # 自检：两个小算例，求解并独立复核
scripts/demo.sh                # 全部 6 个示例，打印汇总表
```

- `scripts/demo.sh` 的独立复核（`tools/eval`）需要 Python 3 与 numpy、scipy；没有时只运行求解器并显示其自身报告。
- Python 接口：`PYTHONPATH=$PWD/python python3 -c "import hsolve"`，需与构建相同的 CPython 次版本（见
  `python/hsolve/` 下扩展模块的文件名，如 `cpython-311`）及 numpy。
- 命令行参数：`bin/hsolve --help`；输入输出格式与配置项见项目的 `docs/FORMATS.md`。

## 目录

| 路径 | 内容 |
|---|---|
| `bin/hsolve` | 命令行求解器（RPATH `$ORIGIN/../lib`） |
| `lib/` | 依赖的共享库：MUMPS 5.8.2（含项目补丁）、OpenBLAS、METIS、SCOTCH、zlib、GCC 运行库 |
| `python/hsolve/` | Python 模块 |
| `examples/` | 6 个示例算例与参考谱（`SHA256SUMS` 校验） |
| `scripts/`、`tools/` | 演示脚本与独立评测器 |
| `licenses/` | 第三方库许可证；`licenses/THIRD_PARTY_BINARIES.md` 列出每个库的来源、版本与许可证 |

许可证：hsolve 以 Apache-2.0 发布（`LICENSE`、`NOTICE`）；随包分发的第三方库各自的许可证见 `licenses/`。

---

## hsolve binary package (Linux x86-64)

Relocatable: unpack anywhere, no conda, compiler or root needed. Requires an x86-64 CPU (SIMD kernels
are chosen at run time) and Linux with glibc >= 2.17. Quick start: the three commands above.
`scripts/demo.sh --quick` is the self-check; its independent evaluation needs Python 3 with numpy and
scipy. Licences: hsolve is Apache-2.0 (`LICENSE`, `NOTICE`); bundled libraries keep their own licences,
listed in `licenses/THIRD_PARTY_BINARIES.md`.
