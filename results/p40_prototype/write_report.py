import difflib,json,shutil
from pathlib import Path
root=Path('~/gencode/os2026');p=Path('/tmp/os2026-p40-local');r=json.loads((p/'collected.json').read_text());a=json.loads((p/'archive-verified.json').read_text())
out=root/'results/p40_prototype';out.mkdir(exist_ok=True)
for base,dest in [(p,out),(p/'v2',out/'v2'),(p/'v3',out/'v3')]:
 dest.mkdir(exist_ok=True)
 for f in base.iterdir():
  if f.is_file() and f.suffix in ['.py','.cpp','.hpp','.inc','.sh','.md']:shutil.copy2(f,dest/f.name)
solvers=['hsolve-base','hsolve-native','hsolve-dd','hsolve-control','hsolve-enclosed','slepc'];cases=list(r['performance'])
order=['syn-near-singular-complex-1e4','syn-near-singular-complex-1e5','syn-wide-range-complex-1e4','syn-zero-cluster-complex-1e4','syn-ghep-zero-cluster-complex-1e4','syn-multiplicity-complex-1e4','yee-photonic-rods-1e4','yee-photonic-spheres-1e4','yee-bloch-1e4']
cases=[c for c in order if c in cases]
head='''# P40：SIMD 残差误差界与线程数实验

**尚未达到全部不慢于开源方案的目标。** 所有构建、数值实验和性能测试均在 gpu02 CPU 上执行。最终候选是 v3；生产保持冻结的 P29。原始汇总见 [p40_measurements.json](p40_measurements.json)，代码和脚本见 [p40_prototype](p40_prototype/)，相对 P37 后端的差异见 [p40_candidate.patch](p40_candidate.patch)。

## 实现

把 P37 的补偿残差修正和 P39 的子问题分解复用合并为 control；enclosed 在此基础上增加 AVX-512 原矩阵残差误差界。根据 Dot2Err 对计算残差构造可靠上界；只有上界不超过原有 1e-12 阈值时才提前通过内部线性求解验收，否则仍计算原 long-double 残差。没有降低容差。

移位探测的残差检查、延迟 MUMPS 回退后的检查、最终特征对的原矩阵残差、满秩检查和 exact 惯性证书保持原样。求解器不把稀疏矩阵转为完整稠密矩阵。

依据 [Ogita、Rump、Oishi 的原文](https://www.tuhh.de/ti3/paper/rump/OgRuOi05.pdf) Algorithm 5.8 / Corollary 5.9；具体缩放系数拆分、下溢余量、分母下界和范围/舍入模式保护见 [数值方法说明](p40_prototype/NUMERICAL_METHOD.md)。

| 版本 | 含义 |
|---|---|
| base | 冻结 P29 |
| native | 冻结 P39 reuse |
| dd | 冻结 P37 dd |
| control | 本轮合并 P37 dd + P39 reuse，未启用新误差界 |
| enclosed | control + v3 SIMD 误差界验收 |

v1 数值检查通过，但反汇编发现编译器在误差界公式中融合乘加，与推导指定的舍入步骤不符。v2 在该函数关闭隐式融合；v3 再增加每个 OpenMP 工作线程的 MXCSR 检查。最终三个对象的反汇编各保留 12 条显式产品误差 FMSUB，未发现该内核中的隐式向量 FMADD。

v3 初版边界检查器漏了 omp.h；修复后另一个断言失败，因为测试假定工作线程的舍入模式会跨并行区保留。独立探针确认 gpu02 的 libgomp 在下一并行区重置该模式。最终检查器验证这一实际行为，没有把它声称为运行中异常工作线程的覆盖；调用者非默认舍入和 FTZ 的回退仍被覆盖。失败的检查器、探针和日志全部保留。

## 正确性
'''
lines=[head]
for ver in ['v1','v2','v3']:
 n=r['numerics'][ver];b=n['boundary-qualified.json'];e=n['enclosure-qualified.json']
 lines.append(f"- {ver}：control/enclosed 各 {n['control']['linear_checks']} 次线性检查全部通过；误差界数组检查 {e['checks']} 次，高精度抽查 {e['decimal_checks']} 点；边界检查 {b['checks']} 次，高精度核对 {b['decimal_components']} 个实/虚分量。")
n=r['numerics']['v3'];b=n['boundary-qualified.json']
lines.append(f"\n最终 v3 边界结果：{b['enclosed']} 次使用误差界、{b['fallback']} 次安全回退、{b['nonfinite']} 次非有限输入检查，其中包括 {b['threshold_checks']} 次阈值两侧分类核对。实际误差/误差半径的最大比值 {b['max_error_over_radius']:.9f}。每个最终版本还覆盖 12 个初始奇异拒绝及 22 个延迟回退输入。独立原始输入残差的评估阈值为 1e-10，与求解器内部保持的 1e-12 门槛不同。")
lines.append('\n最终候选与合并对照共 194 次完整诊断求解，全部有效；包括 34 次小矩阵完整独立参考与预期路径检查、18 次回退契约检查，以及两个 65536 阶稀疏输入各两个版本（显式预算 0.8 GiB）。小型完整稠密参考仅用于测试；两个物理光子晶体的外部参考不完整，仍标记 consistent。')
lines.append('\n| 回归版本 | 调用数 | 通过 | 跳过 | 禁用 | 失败 |\n|---|---:|---:|---:|---:|---:|')
for v,x in r['regression'].items():
 t=x['totals'];lines.append(f"| {v} | {x['summary']['invocations']} | {t.get('passed',0)} | {t.get('skipped',0)} | {t.get('disabled',0)} | {t.get('failed',0)} |")
lines.append('\n每个版本包含 64 个普通测试程序、两项线程/亲和设置、MPI rank=1/2/3/5 和 MPI CLI 检查。OMP2/OpenBLAS1，GPU 隐藏。')
lines.append(f"\n## 线程数探索\n\n先对冻结 P37 dd 和 P39 reuse 的 1/2/4/8/16 线程版本及 SLEPc 执行 9 个主案例 × 3 次重复，共 {r['thread_sweep_attempts']} 次完整求解，全部有效。只有 {sum(r['thread_qualification'].values())}/9 个完整 33 次组通过外部负载资格检查；原始负载中有 {r['thread_monitor'].get('busy_intervals')} 个繁忙区间。三次重复仅作为探索，未据此改变线程策略。逐例资格和全部合格中位数保留在 JSON；受干扰组不用于性能结论。")
thread16=sum(all(data['hsolve-'+base+'-t16']['median_s']<=data['hsolve-'+base+'-t'+str(n)]['median_s'] for n in [1,2,4,8]) for data in r['thread_performance'].values() for base in ['dd','reuse'])
lines.append(f"\n合格案例 × 两个私有版本共有 {2*len(r['thread_performance'])} 组线程对比，其中 {thread16} 组的 16 线程中位数最低。本轮没有支持降低线程数的证据。")
lines.append('''\n## 最终性能比较

固定 6 个版本 × 9 个案例 × 5 次交错重复。CPU16–31、32 GiB、exclusive guard；相同输入、精度和机器。SLEPc 使用 P34 冻结的原生 complex128 + LU 配置。hsolve 计 time_total_s（含最终验证与证书），SLEPc 计 setup+solve+vectors；该求解计时排除进程启动和输入输出。进程墙钟与峰值内存同时保留在 JSON。

启动前要求连续 60 个空闲采样；运行中目标核及其超线程兄弟上的外部负载达到 0.8 CPU，或全机外部负载达到 2 CPU，就判为繁忙。事先规定最多四个批次，仅重测未合格案例的完整 30 次组，选第一个合格组，不选择最快单次或替换已合格组。监控固定在 CPU0；周期采样无法证明操作系统级独占，全部采样保留。
''')
lines.append(f"最终合格 **{len(cases)}/9** 组。\n")
for batch in r['series']['batches']:
 mon=r['candidate_monitors'][batch['tag']];lines.append(f"- {batch['tag']}：返回码 {batch['returncode']}，新增合格 {len(batch['qualified'])} 组，繁忙区间 {mon.get('busy_intervals','未启动')}。")
lines.append('\n合格完整组的求解中位数（秒）：\n\n| 案例 | P29 | P39 reuse | P37 dd | 合并 control | 新 enclosed | SLEPc |\n|---|---:|---:|---:|---:|---:|---:|')
for c in cases:lines.append('| '+c+' | '+' | '.join(f"{r['performance'][c][s]['median_s']:.6f}" for s in solvers)+' |')
lines.append('\n新误差界相对合并对照的变化（正数为耗时降低）：\n\n| 案例 | 耗时降低 | control 范围/s | enclosed 范围/s | enclosed / SLEPc |\n|---|---:|---:|---:|---:|')
for c in cases:
 x=r['performance'][c];co=x['hsolve-control'];en=x['hsolve-enclosed'];pct=(1-en['median_s']/co['median_s'])*100
 lines.append(f"| {c} | {pct:+.1f}% | {co['min_s']:.6f}–{co['max_s']:.6f} | {en['min_s']:.6f}–{en['max_s']:.6f} | {en['time_over_slepc']:.3f}× |")
wins=sum(r['performance'][c]['hsolve-enclosed']['time_over_slepc']<=1 for c in cases)
lines.append(f"\n新候选在合格组中有 {wins}/{len(cases)} 个求解中位数不高于 SLEPc。这里比较的是这一固定参考配置，不能证明比所有开源方案快，也不能把重复区间重叠的小差异认定为稳定收益。目标仍未完成，候选未替换生产。")
lines.append("\n结论：新候选有 5/9 个案例的中位数高于合并对照，不能作为通用性能优化采用。十万阶近奇异案例的总耗时约增加 3.9%，两组重复范围没有重叠；线性求解阶段也从 0.667s 增至 0.694s。广义零点聚簇中位数降低约 9.0%，但范围略有重叠，且不足以抵消其他案例退步。")
lines.append("\n误差界确实被执行：零点聚簇每次 28 次提前通过、十万阶近奇异 18 次、广义零点聚簇 19 次；一万阶近奇异每次 4 次提前通过、1 次回退。宽动态范围案例没有命中误差界，三个物理案例没有进入该后端；这些案例的微小差异不能归因为误差界算法收益。")
lines.append("\n后续重点仍是减少总工作量：十万阶近奇异，合并对照需要 4 次分解和 80 个 RHS，SLEPc 为 1 次分解和 55 个 RHS；零点聚簇为 3 次/112 RHS，对照为 1 次/80 RHS。新误差界没有改变这些计数。若继续研究内部验收，需降低误差界本身的计算成本，同时保留原精度与回退；不能只追求更紧的界。")
lines.append(f"\n全部线程探索、诊断及正式批次合计 **{r['full_solve_valid']}/{r['full_solve_attempts']}** 次有效完整求解；独立参考状态为 {r['valid_completeness']}。原始阶段时间、求解/RHS/分解计数和误差界命中日志均保留。误差界日志为每个后端累积计数，JSON 中简单差分的估计可能低估连续后端，原始计数序列是依据。")
lines.append(f"\n## 归档与复现\n\n生产四个产物和 definite.cpp 的哈希与冻结 P29 一致。没有提交或推送。完整归档本机及 gpu02：`/tmp/os2026-p40-results.tar`，{a['size']} 字节，{a['members']} 个成员；SHA-256 `{a['sha256']}`。下载后验证归档和全部 {a['content_members']} 个内容成员。\n\n包含所有内核版本、失败检查器、编译命令和对象、反汇编、数值输出、完整回归、原始求解记录、资格计划及负载采样。依赖冻结 P29 checkout、P33–P39 私有库/数据及 P28 复数 SLEPc 环境；较大既有输入按内容哈希记录，P38/P39 小型输入随包保留。固定路径重跑需新目录和 tag。比较工具验收完成后按原规则移除完整输出向量。")
(root/'results/p40_measurements.md').write_text('\n'.join(lines)+'\n')
r['archive']=a;(root/'results/p40_measurements.json').write_text(json.dumps(r,indent=2)+'\n')
old=root/'results/p37_prototype/band_backend.hpp';new=out/'v3/band_backend.hpp'
patch=''.join(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='a/results/p37_prototype/band_backend.hpp',tofile='b/results/p40_prototype/v3/band_backend.hpp'))
(root/'results/p40_candidate.patch').write_text(patch)
(out/'README.md').write_text('''# P40 prototype

Final kernel: `v3/band_backend.hpp`, with `v3/residual_enclosure.inc` as its matching standalone excerpt. Build using `v3/build.py`; it consumes frozen P39 `libhsolve-reuse.a` and embeds the P37 DD backend. The supplied patch shows the backend delta relative to P37; P39 sector reuse is a separately frozen dependency.

Earlier v1/v2 kernels and all harness versions are retained. Final boundary commands use `build_boundary_v3.py` and `verify_boundary_v3.py`; final assembly checker is `inspect_assembly_v3.py`, formal launcher `candidate_series_v2.py`. The v3 suffix in those harness filenames is independent of the kernel version.

See ../p40_measurements.md and NUMERICAL_METHOD.md for scope, results and limitations. All builds and numerical tests must run on gpu02 CPU under the existing guard. Do not rerun existing tags/directories, overwrite frozen artifacts or run diagnostic jobs during formal timing.

Full archive is /tmp/os2026-p40-results.tar on both hosts, verified by SHA-256 and every content member. It includes logs and artifacts omitted from this reviewable source directory. Fixed paths require the documented prior-round dependencies.
''')
print(json.dumps(dict(qualified=len(cases),enclosed_wins=wins,files=len(list(out.rglob('*'))))))
