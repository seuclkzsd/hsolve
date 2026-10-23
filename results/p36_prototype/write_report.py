import json
from pathlib import Path

root = Path('~/gencode/os2026')
local = Path('/tmp/os2026-p36-local')
m = json.loads((local/'collected.json').read_text())
archive = json.loads((local/'archive-result.json').read_text())
lines = []
def add(s=''):
    lines.append(s)
def total(tags, solver):
    rows = [m['groups'].get(t,{}).get(solver,{}) for t in tags]
    return f"{sum(r.get('valid',0) for r in rows)}/{sum(r.get('attempts',0) for r in rows)}"

add('# P36：右端打包、SIMD 分解与已检查因子复用')
add()
add('**尚未达到“全部不慢于最快开源方案”的目标。** 本轮在 gpu02 双路 Xeon Silver 4314 的 CPU 上完成实验，生产版本仍为 P29。私有源码、构建命令、完整测试和比较结果均已保存，没有提交或推送。')
add()
add('数据见 [p36_measurements.json](p36_measurements.json)，源码和复现脚本见 [p36_prototype](p36_prototype/)。[p36_candidate.patch](p36_candidate.patch) 记录相对 P33 原生后端的内核和打包变化；最终因子复用的增量在 [checked_reuse.patch](p36_prototype/checked_reuse.patch)。这些文件基于 P35 cappednative 私有库，不能单独当作生产补丁。')
add()
add('## 候选与控制')
add()
add('| 名称 | 相对控制的变化 |')
add('|---|---|')
add('| P29/base | 冻结的现有生产版本 |')
add('| native | 冻结的 P35 cappednative |')
add('| control | 保留原算法的重新编译版，区分编译布局与功能变化 |')
add('| fused | 四 RHS 的缩放、置换、行布局打包及回写合并，去掉两次额外转置 |')
add('| simd | fused 加 AVX-512 复数 Schur 更新；主元选择、交换、对角存储和异常回退仍检查 |')
add('| reuse | simd 加同一位移的已完成分解复用，仍执行原有四 RHS 试探及原问题残差验收 |')
add()
add('复用只保留 status=0、因小主元检测被暂时拒绝的完整因子。普通 solve 在试探激活前仍拒绝使用；只有 alpha/beta 相同的检查路径可激活它。试探要求分量后向误差不超过 1e-12、每个 RHS 的相对残差不超过 sqrt(eps)。试探失败释放因子，精确奇异、独立计数失败和全结果恢复继续走已有回退。')
add()
add('原生调度范围保持为图结构筛选后的窄带复数精确求解；其余输入保留原路径。SIMD 的 FMA 可能改变舍入和主元轨迹，因此不能只靠打包输出一致性证明整条求解路径正确。所有候选保持原 k、容差、最终原问题残差与精确证书要求。')
add()
add('## 正确性结果')
add()
add('| 版本 | 线性检查 | 最大独立分量后向误差 | 精确奇异拒绝 | 延迟回退输入 |')
add('|---|---:|---:|---:|---:|')
for name,r in m['linear_checks'].items():
    add(f"| {name} | {r['valid']}/{r['checks']} | {r['max_eta']:.3e} | {r['singular_rejections']} | {r['fallback_inputs']} |")
add()
add(f"每版使用相同的 320 个输入，覆盖 RHS 数 1、3、4、5、8，非紧密 leading dimension 的保护区、惯性计数与 count 后 solve 拒绝。独立 NumPy/SciPy 扩展精度重算残差。fused 与 control 的 {m['fused_equivalence']['checks']} 组完整线性输出全部逐项相等；reuse 另检查首次分解拒绝后普通 solve 不可用。")
add()
add('| 版本 | 60 个压力输入 | 9 个回退契约 | 9 个常规输入 | 2 个 65536 阶输入 |')
add('|---|---:|---:|---:|---:|')
for v in ['control','fused','simd','reuse']:
    prefix = 'p36-reuse-' if v == 'reuse' else 'p36-'
    groups = [[prefix+s for s in ['stress','holdout','fresh','validation']], [prefix+'contracts'], [prefix+'main'], [prefix+'large']]
    add('| '+v+' | '+' | '.join(total(g,'hsolve-'+v) for g in groups)+' |')
add()
probes = m.get('reuse_probes') or []
accepted = sum(p['reused'] and p['accepted'] for r in probes for p in r['probes'])
rejected = sum(p['reused'] and not p['accepted'] for r in probes for p in r['probes'])
reused = [r for r in probes if any(p['reused'] for p in r['probes'])]
reduced = sum(r['factorizations'] == r.get('simd_factorizations',0)-1 for r in reused)
same_rhs = sum(r['rhs'] == r.get('simd_rhs') for r in reused)
add(f"实际完整求解覆盖 {accepted} 次复用后接受的试探和 {rejected} 次复用后拒绝的试探。{len(reused)} 个出现复用的输入中，{reduced} 个比 simd 少一次分解，{same_rhs} 个 RHS 工作量相同；工作量对照与每例记录保留在 JSON。两例光子晶体外部参考不完整，仅标记 consistent；其余有效结果的完整性按实际参考记录。")
add()
add('| 完整 C++/MPI 回归 | 调用数 | 通过 | 跳过 | 禁用 | 失败 |')
add('|---|---:|---:|---:|---:|---:|')
for name,r in m['regressions'].items():
    t = r['totals']
    add(f"| {name} | {r['invocations']} | {t.get('passed',0)} | {t.get('skipped',0)} | {t.get('disabled',0)} | {t.get('failed',0)} |")
add()
add('每套包含 64 个普通程序、2 个特殊线程/亲和设置、4 个 MPI rank 布局及 1 个 MPI CLI 检查。上述用例数包含单独设置与 MPI 布局的重复身份。采用 CMake 注册环境 OMP_NUM_THREADS=2、OPENBLAS_NUM_THREADS=1，并隐藏 GPU。正确性诊断固定 CPU 8–15、12 GiB；其耗时不作合格速度结论。')
add()
add('## 同机完整求解计时')
add()
add('正式批次固定 CPU 16–31、16 个物理核、32 GiB、exclusive guard，9 个算例、7 个版本、每版 5 轮交错。SLEPc 使用已验证的 P28 原生 complex128 + LU 逐例配置和 P29 Bloch 配置。hsolve 计完整 time_total_s，含检查及证书；SLEPc 计 setup+solve+vectors。双方均排除启动和输入输出，CLI 墙钟另存。SLEPc nearest 不执行同一惯性证书，但按同一原问题和容差独立验收。')
add()
monitor = m['monitor'] or {}
add(f"启动前要求连续 60 个空闲采样。运行期目标核及其超线程兄弟累计外部负载达到 0.8 CPU，或全机达到 2 CPU，则标记繁忙。记录 {monitor.get('busy_intervals','未知')} 个繁忙区间；{sum(m['qualified_cases'].values())}/9 个完整组满足全部 35 次有效且未命中繁忙采样。周期 /proc 采样不能证明操作系统级独占，所有采样保留。")
add()
if m['performance']:
    add('下表仅列合格组，单位为完整求解秒，中位数；所有最小值、最大值、墙钟、误差、内存与阶段统计均在 JSON 中。')
    add()
    names = ['hsolve-base','hsolve-native','hsolve-control','hsolve-fused','hsolve-simd','hsolve-reuse','slepc']
    add('| 算例 | P29 | native | control | fused | simd | reuse | SLEPc |')
    add('|---|---:|---:|---:|---:|---:|---:|---:|')
    for case,stats in m['performance'].items():
        add('| '+case+' | '+' | '.join(f"{stats[n]['median_s']:.6f}" for n in names)+' |')
    add()
    add('| 算例 | reuse 相对 P35 耗时变化 | reuse / SLEPc | reuse 范围 | SLEPc 范围 |')
    add('|---|---:|---:|---:|---:|')
    for case,stats in m['performance'].items():
        r,s = stats['hsolve-reuse'],stats['slepc']
        add(f"| {case} | {(r['time_over_native']-1)*100:+.1f}% | {r['time_over_slepc']:.3f} | {r['min_s']:.6f}–{r['max_s']:.6f} | {s['min_s']:.6f}–{s['max_s']:.6f} |")
    add()
    for v in ['fused','simd','reuse']:
        wins = sum(s['hsolve-'+v]['median_s'] <= s['slepc']['median_s'] for s in m['performance'].values())
        add(f"{v} 在 {len(m['performance'])} 个合格组中有 {wins} 个中位数不高于本轮 SLEPc。")
    add()
    add('这些是指定输入和配置的五轮结果，小幅差异需结合范围判断，不能推及所有输入或所有开源求解器。光子晶体走原有路径，本轮内核优化未消除其重复分解和认证成本。')
else:
    add('本批次没有完整合格组，不从受干扰样本中选择最快时间作速度结论。')
add()
add('## 归档、范围与后续缺口')
add()
add(f"共记录 {m['full_solve_attempts']} 次完整求解，{m['full_solve_valid']} 次有效；有效参考状态为 {m['valid_completeness']}。生产 definite.cpp 和四个生产产物哈希未变。初始 continuation 返回 75 是为追加 reuse 候选主动延后计时，先前两套回归已经成功，并非数值失败。")
add()
add('所有编译、数值检查与性能求解均在 gpu02 进行。本地仅编辑、解析日志和核对归档。候选使用 -march=native，当前是 gpu02 私有原型；生产集成仍需独立模块、运行时指令集分派及通用路径。原生结构覆盖之外的真实光子晶体、大型精确计数和其他输入仍有性能缺口。')
add()
add(f"本机及 gpu02 保存 `{archive['path']}`，{archive['size']} 字节、{archive['members']} 个成员，SHA-256 `{archive['sha256']}`。下载后核对整个归档及全部 {archive['content_members']} 个内容成员。包含源码、二进制、构建命令、线性输出、C++/MPI 日志、完整求解报告、负载采样、工具快照和输入哈希。沿用的 P33/P34/P35 输入保存在各轮归档或共享输入树，本轮没有生成新数值输入。比较工具按原流程在独立评估后删除特征向量。")
add()
add('复现依赖已有 P29 checkout、P35 cappednative 库、P33/P34/P35 输入与 P28 SLEPc 环境。脚本包含固定路径，重跑必须另建输出目录和 tag。报告没有将共享核诊断时间用于加速比，也没有声称已超过最快开源方案。')
(root/'results/p36_measurements.md').write_text('\n'.join(lines)+'\n')
(root/'results/p36_measurements.json').write_text(json.dumps(m,indent=2)+'\n')
print('P36 report written from audited records.')
