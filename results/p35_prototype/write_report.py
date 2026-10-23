import json
from pathlib import Path

root=Path('~/gencode/os2026')
local=Path('/tmp/os2026-p35-local')
m=json.loads((local/'collected.json').read_text())
archive=json.loads((local/'archive-result.json').read_text())
lines=[]
def add(s=''):
    lines.append(s)
def total(tags, solver):
    rows=[m['groups'].get(t,{}).get(solver,{}) for t in tags]
    return sum(r.get('valid',0) for r in rows),sum(r.get('attempts',0) for r in rows)

add('# P35：存储复用、预算边界与追加求解实验')
add()
add('**尚未达到“全部不慢于最快开源方案”的目标。** 本轮在 gpu02 双路 Xeon Silver 4314 的 CPU 上完成实验，生产版本仍为 P29。私有实现和失败记录均保留，没有提交或推送。')
add()
add('数据见 [p35_measurements.json](p35_measurements.json)，源码与复现脚本见 [p35_prototype](p35_prototype/)。[p35_candidate.patch](p35_candidate.patch) 是 packed 相对当前生产驱动的差异；后续限量追加的差异单列在 [bounded_rerun.patch](p35_prototype/bounded_rerun.patch)。')
add()
add('## 实现与验证口径')
add()
add('`packed` 基于 P34 accepted，复用残差修正的三个工作向量，按原顺序在已有 X/AX/BX 中压紧保留列和传递修正后的向量，并移除逐步 stderr 调试输出。nearest 保持原容差的严格筛选；window 保留原来的 10 倍阈值。原地缩小列数会保留 vector 容量，因此不能仅凭减少分配次数断言所有输入的峰值内存都会下降。')
add()
add('新增 65536 阶 HEP/GHEP 压力输入暴露了窗口内补算过多的问题。`capped` 在仍有选中向量未达原残差要求、且窗口要求补算超过 k 时，先额外尝试一次最多 k 个前导对的追加求解，再重新选择、验证和认证。若仍未完成，后续恢复完整计数需求，保留大重根簇的处理能力；这一次额外尝试不扣除原有两次重跑机会。native 后缀表示叠加 P33 私有原生后端及其 MUMPS 回退。')
add()
add('所有构建、数值输入生成、测试与求解均在 gpu02 执行。本地仅编辑、解析记录与核对哈希。正确性诊断固定 CPU 8–15、12 GiB，原始共享核时间不作速度胜负依据。没有减少请求的 k、放宽容差或把 certificate.passed 单独当作完整验收。')
add()
add('## 正确性与预算')
add()
add('| 候选 | 原有 60 个压力输入 | 9 个常规输入 |')
add('|---|---:|---:|')
for name,prefix in [('packed','p35-'),('packednative','p35-'),('capped','p35-capped-'),('cappednative','p35-capped-')]:
    pressure=total([prefix+x for x in ['stress','holdout','fresh','validation']],'hsolve-'+name)
    main=total([prefix+'main'],'hsolve-'+name)
    if pressure[1] or main[1]:add(f'| {name} | {pressure[0]}/{pressure[1]} | {main[0]}/{main[1]} |')
add()
add('两个光子晶体算例只有不完整外部参考，验收状态为 consistent，其余常规输入为 complete。新增大输入为已知完整谱、随机耦合的 65536 阶复数 HEP/GHEP，近重根数 24、k=28、间隔 2^-30；GHEP 的质量矩阵条件数参数为 32。')
add()
add('| 显式预算批次 | accepted | packed | acceptednative | packednative |')
add('|---|---:|---:|---:|---:|')
for tag,group in m['groups'].items():
    if not tag.startswith('p35-budget-'):continue
    values=[f"{group.get(s,{}).get('valid',0)}/{group.get(s,{}).get('attempts',0)}" for s in ['hsolve-accepted','hsolve-packed','hsolve-acceptednative','hsolve-packednative']]
    add('| '+tag.removeprefix('p35-budget-')+' | '+' | '.join(values)+' |')
add()
original=[r for r in m['budget_pairs'] if r['candidate']['solver'] in ['hsolve-packed','hsolve-packednative']]
add(f"原存储复用实验共 {len(original)} 个同输入、同预算的版本配对；其中 {sum(r['validity_regression'] for r in original)} 个出现旧版有效而新版无效。低预算下有拒绝求解和超时，不能全部归为精度退化。")
add()
add('**显式预算与峰值 RSS 分开统计。** 旧版和新版都有结果有效但峰值超过显式预算的运行；求解器预算用于规划，并非实测峰值的硬上界。外层 guard 的 12 GiB 上限始终保留。此批次未发现有效性回退，仍不能证明所有未来输入都无容量保留问题。')
add()
add('| 完整 C++ 回归 | 调用数 | 通过 | 跳过 | 禁用 | 失败 |')
add('|---|---:|---:|---:|---:|---:|')
for name,r in m['regressions'].items():
    t=r['totals']
    add(f"| {name} | {r['invocations']} | {t.get('passed',0)} | {t.get('skipped',0)} | {t.get('disabled',0)} | {t.get('failed',0)} |")
add()
add('每套含 64 个普通程序、2 个特殊线程/亲和设置、4 个 MPI rank 布局及 1 个 MPI CLI 失败处理检查。用例数含单独重跑的设置和 MPI 布局，并非独立测试身份的数量。环境遵循 CMake：OMP_NUM_THREADS=2、OPENBLAS_NUM_THREADS=1，GPU 设备隐藏。P34 在 OMP=8/OpenBLAS=8 下复现的两项基线失败在本环境中没有复现；不能把两轮当作相同线程设置。')
add()
add('## 合格性能对照')
add()
add('CPU 16–31、16 个物理核、32 GiB、exclusive guard，九个算例、六个版本、五轮交错。SLEPc 使用 P28 原生 complex128 + LU 的逐例调优配置及 P29 通过精度验证的 Bloch 配置。hsolve 计完整 time_total_s，含残差检查与证书；SLEPc 计 setup+solve+vectors。双方均排除进程启动与输入输出，CLI 总墙钟另存于 JSON。SLEPc nearest 不执行相同的惯性证书，其结果仍按同一个原问题和容差独立验收。')
add()
monitor=m['monitor'] or {}
add(f"启动前要求连续 60 个空闲采样；运行期目标核及其超线程兄弟达到 0.8 个外部 CPU，或全机达到 2 个外部 CPU，即标忙。运行期记录 {monitor.get('busy_intervals','未知')} 个繁忙区间；{sum(m['qualified_cases'].values())}/9 个完整算例组符合全部 30 次有效且无所测负载干扰的条件。周期 /proc 采样不能证明操作系统级独占，所有采样保留。")
add()
if m['performance']:
    add('下表仅列合格组，中位数单位为秒。accepted 是 P34 对照，packed 是存储复用版。')
    add()
    names=['hsolve-base','hsolve-accepted','hsolve-packed','hsolve-acceptednative','hsolve-packednative','slepc']
    add('| 算例 | P29 | accepted | packed | acceptednative | packednative | SLEPc |')
    add('|---|---:|---:|---:|---:|---:|---:|')
    for case,stats in m['performance'].items():
        add('| '+case+' | '+' | '.join(f"{stats[n]['median_s']:.6f}" for n in names)+' |')
    add()
    for solver in ['hsolve-packed','hsolve-packednative']:
        n=sum(stats[solver]['median_s']<=stats['slepc']['median_s'] for stats in m['performance'].values())
        add(f"{solver} 在 {len(m['performance'])} 个合格组中有 {n} 个中位数不高于本轮 SLEPc。小于几百分点的差别不能单凭五轮中位数断言稳定收益；本轮也未覆盖全部开源求解器。")
else:
    add('本批次未获得可用于速度胜负结论的完整组；不从受干扰或无效批次挑最快样本。')
add()
add('## 限量追加的后续实验')
add()
for tag,group in m['groups'].items():
    if tag.startswith('p35-capped-large-'):
        add(tag+'：'+ '，'.join(f"{s} {v['valid']}/{v['attempts']} 有效" for s,v in group.items())+'。')
add()
add('| 新大输入（MUMPS 路径） | 显式预算 GiB | packed | capped 诊断求解秒 | 最大独立误差 | 峰值 GiB |')
add('|---|---:|---|---:|---:|---:|')
for pair in m['budget_pairs']:
    if pair['candidate']['solver']!='hsolve-capped':continue
    work=next(r for r in m['work_examples'] if r['out']==pair['candidate']['out'])
    done=[r for r in work['events'] if r.get('event')=='done']
    seconds=f"{done[-1]['seconds']:.3f}" if done else '未完成'
    control='有效' if pair['control']['valid'] else '失败/超时'
    eta=f"{work['max_eta']:.3e}" if work['max_eta'] is not None else '—'
    add(f"| {pair['case']} | {pair['budget_gib']} | {control} | {seconds} | {eta} | {pair['candidate']['peak_gib']:.3f} |")
add()
add('65536 阶 HEP、0.4 GiB 显式预算的旧路径：原窗口计数 534，缩窗后仍为 185，发现 27 个、4 个选中向量尚未达标，要求补算 158 个。capped 将这一次的前导追加目标限制为 28（Ritz 请求 30），追加迭代完成于 525 次算子应用，之后精确计数为 28、找到 28，独立完整谱与原残差验收通过。它仍可能超过显式预算，表中保留实际峰值。')
add()
add('这些时间属于 8 核正确性与工作量诊断，不能据此计算合格加速比或宣称超过开源方案。两档预算的旧 MUMPS 控制均在 60 秒时限结束，新候选在时限内完成；原生控制本来就能完成。完整窗口、追加目标和工作量见 JSON 的 work_examples，全部成功与失败均保留。')
add()
add('## 尚存的性能缺口')
add()
add('合格重根组的 packednative 分析中位数约 0.00181 s，回代 0.05924 s，三次分解共 0.03042 s；SLEPc 一次分解约 0.02472 s。零点聚簇的原生候选仍做四次分解、112 个 RHS，SLEPc 为一次分解、80 次回代；两例光子晶体仍为三次对一次分解。阶段统计与完整求解时间共同表明，减少临时分配尚不足以消除分解、回代和认证成本。阶段中位数独立统计，不要求相加等于总时间中位数。')
add()
add('## 总数与归档')
add()
add(f"共保留 {m['full_solve_attempts']} 次完整求解尝试，{m['full_solve_valid']} 次有效；有效结果的参考状态为 {m['valid_completeness']}。这与上面的分组有重叠，不重复相加。生产源码和四个生产产物的哈希保持不变。")
add()
add(f"本机及 gpu02 保存 `{archive['path']}`，{archive['size']} 字节、{archive['members']} 个成员，SHA-256 `{archive['sha256']}`。下载后核对整个归档及全部 {archive['content_members']} 个内容成员。归档包含私有源码、构建命令、二进制、完整测试日志、新大输入和参考谱、全部求解报告、负载记录、工具快照和输入哈希。既有压力输入位于 P34 归档；标准输入及旧压力输入在本轮记录哈希。比较工具按原流程在独立评估后删除完整特征向量。")
add()
add('复现依赖已有 P29 checkout、P33 原生库、P34 压力输入和 P28 SLEPc 环境。脚本使用固定路径，重跑应另建输出目录与 tag。仍需处理真实光子晶体、大型精确计数及其他未达标输入；本轮证据不支持“已全部超过最快开源方案”。')
(root/'results/p35_measurements.md').write_text('\n'.join(lines)+'\n')
(root/'results/p35_measurements.json').write_text(json.dumps(m,indent=2)+'\n')
print('P35 report written from audited records.')
