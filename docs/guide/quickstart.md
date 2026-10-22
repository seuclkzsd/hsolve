# 快速开始

十分钟内装好 hsolve，求出一个方波导的全部传播模，并读懂结果。只需要一台 Linux x86-64 机器，不需要 GPU、MPI
或 root 权限。

## 1. 安装

=== "容器镜像"

    不需要编译，适合先看效果：

    ```bash
    docker run --rm {{TODO:rb-eng 的镜像名与标签，例如 ghcr.io/seuclkzsd/hsolve:1.0.0}} {{TODO:rb-eng 的演示命令}}
    ```

    镜像内置样例：依次求解、用独立评测器复核，并打印结果表。

=== "Release 二进制包"

    ```bash
    curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/{{TODO:rb-eng 的压缩包名}}
    curl -LO https://github.com/seuclkzsd/hsolve/releases/download/v1.0.0/{{TODO:rb-eng 的 SHA256SUMS 文件名}}
    sha256sum -c {{TODO:rb-eng 的 SHA256SUMS 文件名}} --ignore-missing
    tar xf {{TODO:rb-eng 的压缩包名}}
    ```

    压缩包是可移植构建（不依赖构建机的指令集），解压即可运行其中的 `hsolve`。

=== "从源码构建"

    需要 conda（推荐 [Miniforge](https://github.com/conda-forge/miniforge)），全部依赖来自 conda-forge：

    ```bash
    git clone https://github.com/seuclkzsd/hsolve.git && cd hsolve
    conda env create -f env/environment.yml && source env/activate.sh
    tools/dev/build.sh portable
    ```

    构建先由仓库自带的 MUMPS 5.8.2 官方源码包编译打过补丁的 MUMPS（只在第一次，之后按输入哈希复用），再编译
    hsolve。产物在 `build/portable/`：命令行 `hsolve` 与 Python 模块 `build/portable/python/hsolve`。
    `tools/dev/build.sh release` 则为本机指令集优化（`-march=native`），适合在同一台机器上长期使用。

下文的命令假设在源码目录中、已经 `source env/activate.sh`，`hsolve` 指 `build/portable/hsolve`。

## 2. 第一次求解：10 mm 方波导在 50 GHz 的传播模

10 mm × 10 mm 的空心金属方波导，TEₘₙ 与 TMₘₙ 模的截止频率为 f_c = c·√(m² + n²) / (2a) ≈ 15·√(m² + n²) GHz。
在 50 GHz 下 √(m² + n²) < 3.33 的模都能传播：TE 模 12 个、TM 模 6 个，共 18 个。用仓库里的有限元生成器
（Lee–Sun–Cendes 棱元-节点元混合公式）离散这个问题，再求 λ = −β² 最靠近 −0.5 mm⁻² 的 18 个特征值：

```bash
python -m tools.gen.waveguide --family waveguide --a 10 --b 10 --freq 50 --target-n 20000 --name wg-square-2e4
build/portable/hsolve --A data/cases/wg-square-2e4/A.npz --B data/cases/wg-square-2e4/B.npz \
    --sigma -0.5 --k 18 --out out/wg-square-2e4
```

这是一个 B **不定**的广义问题（GHIEP），而且 A 有维数与内部节点数相同的零空间。hsolve 自动识别这两点：问题类型
由 B 的正定性检验自动判定，零空间由单边位移排除，返回的是 18 个传播模，而不是一串零。

## 3. 读结果

结果目录里有三个文件：

| 文件 | 内容 |
|---|---|
| `eigenvalues.npy` | 特征值，按离 σ 由近到远排序 |
| `eigenvectors.npy` | 特征向量，n × m，Fortran 序 |
| `report.json` | 每个特征对的残差与后向误差、完备性证书、各阶段计时、峰值内存、告警 |

把特征值换成传播常数 β = √(−λ)（单位 mm⁻¹），并与解析值比较：

```python
import numpy as np
lam = np.sort(np.load("out/wg-square-2e4/eigenvalues.npy"))
ref = np.sort(np.load("data/refs/wg-square-2e4/eigenvalues.npy"))   # 连续模型的解析值
for l, r in zip(lam, ref[ref < 0]):
    print(f"beta = {np.sqrt(-l):.6f} mm^-1   analytic {np.sqrt(-r):.6f}   rel. diff {abs(l - r) / abs(r):.1e}")
```

离散解与解析值的差别来自有限元离散（随网格加密按 h² 减小），而不是求解器。要判断求解本身是否可信，看
`report.json`：

```bash
python -c "import json; r = json.load(open('out/wg-square-2e4/report.json')); \
print(r['success'], max(p['backward_error'] for p in r['pairs']), r['certificate']['note'])"
```

`success` 为真表示每个特征对的后向误差都不超过容差（默认 1e-10）。B 不定时 Sylvester 惯性不能计数，
`certificate` 会写明「证书不可用」；B 正定或 B = I 的问题则给出完备性证书。字段的完整解释见
[结果解读与诊断](diagnostics.md)。

## 4. 在 Python 中使用

```python
import numpy as np, scipy.sparse as sp
import hsolve                                    # PYTHONPATH=build/portable/python

n = 2000
A = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1], format="csr")
res = hsolve.solve(A, sigma=1.0, k=6)            # 1.0 附近最近的 6 个特征值
print(res.success, res.eigenvalues)
print(res.report["certificate"]["statement"])    # B = I：完备性证书的文字陈述
```

`hsolve.solve` 接受 SciPy 稀疏矩阵、NumPy 数组或矩阵文件路径，返回 NumPy 数组；与命令行走同一条求解路径、
用同一份配置格式。详见 [Python 接口](../PYTHON.md)。

## 5. 接下来

- [命令行](cli.md)：全部求解目标（区间、两端）、常用选项、配置文件与环境变量。
- [结果解读与诊断](diagnostics.md)：`report.json` 的字段、退出码、常见问题的处置。
- [算法原理概览](algorithms.md)：位移反演、块 Krylov-Schur 与完备性证书。
- [评测方法](evaluation.md)：怎样独立复核结果、怎样与 SLEPc 公平对比。
