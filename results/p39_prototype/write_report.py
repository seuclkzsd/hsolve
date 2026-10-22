import json
from pathlib import Path
root=Path('/home/zhlin/gencode/os2026');p=Path('/tmp/os2026-p39-local')
m=json.loads((p/'collected.json').read_text());archive=json.loads((p/'archive-verified.json').read_text());lines=[]
def add(s=''):lines.append(s)
add('# P39：直接调用子问题 Lanczos，并复用分析和分解')
add()
add('**尚未达到全部不慢于开源方案的目标。** 本轮只在 gpu02 CPU 上构建和运行。实现、独立验收、完整回归及性能比较状态记录如下；生产仍为 P29。数据见 [p39_measurements.json](p39_measurements.json)，源码见 [p39_prototype](p39_prototype/)，相对 P38 的实现差异见 [p39_candidate.patch](p39_candidate.patch)。')
add()
add('## 改动')
add()
add('P38 自适应部分 Bloch 路径在追加候选时再次进入完整求解器，重复建立问题、分析和分解。P39 将稀疏子矩阵、范数估计、B 正定性判断与分解状态放在本次候选构造的局部状态中，直接调用现有 Lanczos、Rayleigh–Ritz 和残差补救实现。没有进程级缓存。')
add()
add('| 版本 | 用途 |')
add('|---|---|')
add('| control | 重新编译 P38 adaptive 算法，作为构建对照 |')
add('| direct | 直接进入既有 Lanczos，追加时重新分析和分解 |')
add('| reuse | 在 direct 基础上保留各子问题的分解，追加时复用实际分解位置 |')
add('| native / base / scalar / dd | 冻结的 P38 adaptive、P29、P37 scalar、P37 dd |')
add()
add('每个小子问题采用 1 个线程，较大子问题最多 4 个线程，作用域退出时恢复调用者线程数。候选向量和稀疏工作区预算扣除后，剩余预算的 80% 按子问题数分配给各分解，同时保留原 MUMPS 内存上限检查。所有分解在提升向量和执行外层证书前释放。零模过滤选项直接走原候选路径。')
add()
add('周期识别仍只读取实际 A/B 的 CSR，检查共同扭转平移关系，支持周期 3–64。子问题仍为稀疏矩阵，求解器不做完整稠密化。子问题结果仅作为候选，最终原矩阵残差、满秩检查和 exact 惯性证书保持原样；球状输入的 B 不满足该结构，继续原路径。')
add()
add('## 验收与工作量')
add()
diagnostics={k:v for k,v in m['groups'].items() if k not in ['p39-screen','p39-recheck','p39-recheck2','p39-recheck3']}
attempts=sum(v['attempts'] for group in diagnostics.values() for v in group.values())
valid=sum(v['valid'] for group in diagnostics.values() for v in group.values())
add(f'诊断与补充检查共 {attempts} 次完整求解，{valid} 次有效。包括 9 次初步检查、205 次常规诊断和 6 次补充检查（初版及修正用例各 3 次）。覆盖原有压力输入、私有后端回退契约、9 个主算例，以及两个 65536 阶输入（显式预算 0.8 GiB）。')
add()
add(f"小矩阵路径检查共 {len(m['small_cases'])} 次，direct/reuse 各 17 次，均通过完整独立参考和预期路径检查。新增输入包含目标恰在特征值上、提高 k、重复特征值、零模过滤，以及强制每个子问题追加候选。完整稠密参考只用于阶数不超过 420 的测试矩阵，符合 DESIGN 的测试例外。另有 {len(m['contracts'])} 次私有后端完整求解契约检查通过。")
add()
b=m['budget']
add(f"预算与线程恢复检查 4/4：零预算、NaN 预算和 2 MiB 预算拒绝该候选路径，128 MiB 预算成功；每次调用后均恢复为调用前的 4 个线程。成功结果 6 对，原矩阵最大后向误差 {b['max_eta']:.3e}，B 正交误差 {b['b_orthogonality']:.3e}，完整参考集合误差 {b['reference_set_error']:.3e}。")
add()
extra=m['extra_checks']
add(f"目标位置检查：请求 sigma={extra['requested_shift']:.17g}；发现 {len(extra['perturbed_reuse'])} 次实际移动位置后的缓存复用。逐条检查其位置与首次成功分解完全相同，追加时分析和分解计数均为零。")
add()
add('| 回归版本 | 调用数 | 通过 | 跳过 | 禁用 | 失败 |')
add('|---|---:|---:|---:|---:|---:|')
for variant,r in m['regression'].items():
 t=r['totals'];add(f"| {variant} | {r['summary']['invocations']} | {t.get('passed',0)} | {t.get('skipped',0)} | {t.get('disabled',0)} | {t.get('failed',0)} |")
add()
add('每个版本包括 64 个普通测试程序、2 个线程/亲和设置、MPI rank=1/2/3/5 和 1 个 MPI CLI 检查。计数包含不同设置下重复执行的测试身份；OMP2/OpenBLAS1，GPU 隐藏。')
add()
add('| 杆状主案例版本 | 子问题调用 | 分析 | 分解 | RHS | 累计请求候选对 |')
add('|---|---:|---:|---:|---:|---:|')
for w in m['modal_work']:
 if w['case']=='yee-photonic-rods-1e4' and '/p39-main/' in w['out']:
  add(f"| {w['solver']} | {w['inner_calls']} | {w['inner_analyses']} | {w['inner_factorizations']} | {w['inner_rhs']} | {w['requested_pair_sum']} |")
add()
add('这里减少的是子问题重复分析和分解，不是整个求解器的耗时比例。原矩阵两次 exact 证书计数仍存在。外层 time_total_s/time_iterate_s 包含全部内层计算，外层 factor_stats 不包含内层分解，因此单独保留所有子问题 stderr 记录及汇总。两个物理光子晶体仍标为 consistent，不冒充完整独立参考验收。')
add()
add('补充移动位置用例初版请求 k=20，超出周期识别要求 n_sector >= 2k+4（32 < 44），三个版本均正确回退并通过完整参考，但路径断言失败。修正用例使用 k=14，恰好满足尺寸限制，同时让首轮 14 对候选全部处于追加半径内。保留两个用例及初版失败记录；求解器源码未变。')
add()
add('初版预算检查器误以为 CLI 链接只有一个入口对象，在编译前失败。budget_check_v2 改用单入口基准程序的链接命令后通过；求解器源码未因此改动，初版失败日志和两个检查器版本均保留。')
add()
add('## 性能比较')
add()
add('预设 8 个版本 × 9 个主算例 × 5 次交错重复，共 360 次。CPU16–31、32GiB、exclusive guard，使用同一 gpu02、同一输入和精度。SLEPc 使用 P34 固定的原生 complex128 + LU 配置；hsolve 计完整 time_total_s，含验证和证书；SLEPc 计 setup+solve+vectors，均排除进程启动与输入输出。')
add()
monitor=m['monitor']
if monitor.get('benchmark_started') is False:
 add(f"**正式测速未启动。** {monitor['elapsed_s']:.1f} 秒内未得到所需的 60 个连续空闲采样，监控返回 {monitor['returncode']}。本轮没有合格加速比，诊断耗时不用于声称优于旧版或 SLEPc。")
else:
 add(f"监控记录 {monitor.get('busy_intervals')} 个繁忙区间；{sum(m['batch_qualification']['p39-screen'].values())}/9 个首批完整算例组通过有效性和负载检查。每组要求所有 40 次求解有效且未命中繁忙区间。")
add()
add(f"首批之后仅对受干扰的重复谱、广义零点聚簇和 Bloch 三组完整补测，每组仍为 8 个版本 × 5 次；原始结果全部保留。补测实际启动：{m['recheck_monitor'].get('benchmark_started',True)}；补测合格 {sum(m['batch_qualification']['p39-recheck'].values())}/3 组。之后仅对仍受干扰的重复谱和广义零点聚簇两组再次完整补测，合格 {sum(m['batch_qualification']['p39-recheck2'].values())}/2 组。最后只对重复谱再次完整补测，合格 {sum(m['batch_qualification']['p39-recheck3'].values())}/1 组。最终合格 {sum(m['qualified_cases'].values())}/9 组，每组只选一个完整批次；原批次已合格组不替换，不挑选更快单次样本。")
add()
add('判据在运行前固定：目标核或其超线程兄弟上的外部负载达到 0.8 CPU，或全机外部负载达到 2 CPU，就标记繁忙。监控固定在 CPU0，并排除自身及受控作业。周期 /proc 采样不能证明操作系统级独占，全部原始样本已保留。')
if m['performance']:
 add();add('合格完整组的求解中位数（秒）：');add()
 names=['hsolve-base','hsolve-native','hsolve-control','hsolve-scalar','hsolve-dd','hsolve-direct','hsolve-reuse','slepc']
 add('| 算例 | P29 | P38 native | control | scalar | dd | direct | reuse | SLEPc |')
 add('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
 for case,s in m['performance'].items():add('| '+case+' | '+' | '.join(f"{s[n]['median_s']:.6f}" for n in names)+' |')
add()
add(f"本轮全部批次合计 {m['full_solve_attempts']} 次完整求解、{m['full_solve_valid']} 次有效；独立参考状态为 {m['valid_completeness']}。全部候选和对照的合格中位数与区间保留在 JSON；不因微小中位数差异就宣称稳定收益。")
add()
perf=m['performance']
if 'yee-photonic-rods-1e4' in perf:
 r=perf['yee-photonic-rods-1e4'];cache=r['hsolve-reuse'];control=r['hsolve-control']
 add(f"杆状案例：P29 {r['hsolve-base']['median_s']:.6f}s → P38 control {control['median_s']:.6f}s → P39 reuse {cache['median_s']:.6f}s，SLEPc {r['slepc']['median_s']:.6f}s。P39 比 P38 的中位数低 {(1-cache['median_s']/control['median_s'])*100:.1f}%，但重复区间重叠，不能把这点差异认定为稳定提升；比 SLEPc 仍慢 {(cache['time_over_slepc']-1)*100:.1f}%。")
 add()
for case in ['syn-zero-cluster-complex-1e4','syn-near-singular-complex-1e5']:
 if case in perf:
  r=perf[case];dd=r['hsolve-dd'];control=r['hsolve-control']
  add(f"{case}：P37 dd 残差候选 {dd['median_s']:.6f}s，比同批 control 中位数低 {(1-dd['median_s']/control['median_s'])*100:.1f}%；SLEPc 为 {r['slepc']['median_s']:.6f}s，仍慢 {(dd['time_over_slepc']-1)*100:.1f}%。这是此前残差优化本轮首次取得的合格对比，不是 P39 缓存路径在这些输入上的收益。")
  add()
add('此前 [P36 合格数据](p36_measurements.md) 中的零点聚簇、广义零点聚簇和物理光子晶体差距仍需解决。本轮的工作量削减没有证明全部端到端性能达标，也没有验证优于所有开源实现。')
add()
add('## 复现与归档')
add()
add(f"生产四个产物及 definite.cpp 的哈希与冻结 P29 一致。原型未集成到生产、提交或推送。完整归档在本机和 gpu02：`{archive['path']}`，{archive['size']} 字节，{archive['members']} 个成员；SHA-256 `{archive['sha256']}`。下载后核验归档本身及全部 {archive['content_members']} 个内容成员。")
add()
add('归档含三个私有版本的源码、构建命令和产物，全部诊断/验收/回归日志，预算及线程检查，P38 和 P39 小矩阵与独立参考，原始负载采样、工具快照、生产哈希与输入/依赖哈希。复现仍依赖冻结 P29 checkout、P33–P38 私有库和数据以及 P28 复数 SLEPc 环境；固定路径重跑须使用新目录和 tag。独立验收后，比较工具按既有规则删除完整输出向量。')
(root/'results/p39_measurements.md').write_text('\n'.join(lines)+'\n')
(root/'results/p39_measurements.json').write_text(json.dumps(m,indent=2)+'\n')
print('P39 report written.')
