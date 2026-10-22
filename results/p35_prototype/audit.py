import collections
import hashlib
import json
import statistics
from pathlib import Path

p = Path('/tmp/os2026-p35')
repo = Path('/tmp/os2026-p10-repair.9doyhO')

def read(f):
    return json.loads(f.read_text())

def digest(f):
    h = hashlib.sha256()
    with f.open('rb') as src:
        for block in iter(lambda: src.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def tag(row):
    return Path(row['out']).relative_to(repo / 'results/raw').parts[0]

runs = [json.loads(line) for line in (p / 'runs.jsonl').read_text().splitlines()]
assert len({r['out'] for r in runs}) == len(runs), 'Overwritten run directory'
groups = {}
for row in runs:
    group = groups.setdefault(tag(row), {}).setdefault(row['solver'], dict(attempts=0, valid=0, failures=[]))
    group['attempts'] += 1
    if row['valid']:
        assert row['completeness'] in ['complete', 'consistent']
        group['valid'] += 1
    else:
        group['failures'].append({k: row.get(k) for k in ['case', 'out', 'why', 'error', 'max_eta', 'pairs']})
    assert row['ended_monotonic'] >= row['started_monotonic']

regressions = {}
for variant in ['base', 'packed', 'packednative', 'capped', 'cappednative']:
    root = p / ('full-' + variant)
    if not (root / 'summary.json').exists():
        continue
    rows = read(root / 'results.json')
    totals = collections.Counter()
    failures = []
    skips = []
    for row in rows:
        f = root / (row['target'] + '.json')
        if not f.exists():
            assert row['target'] == 'mpi-cli-helper-log'
            continue
        data = read(f)
        for suite in data['testsuites']:
            for case in suite['testsuite']:
                identity = row['target'] + ':' + suite['name'] + '.' + case['name']
                totals['listed'] += 1
                if case.get('failures'):
                    totals['failed'] += 1
                    failures.append(dict(test=identity, failures=case['failures']))
                elif case.get('result') == 'SKIPPED':
                    totals['skipped'] += 1
                    skips.append(dict(test=identity, reasons=case.get('skipped')))
                elif case.get('status') == 'NOTRUN' or case.get('result') == 'SUPPRESSED':
                    totals['disabled'] += 1
                elif case.get('status') == 'RUN' and case.get('result') == 'COMPLETED':
                    totals['passed'] += 1
                else:
                    raise AssertionError(case)
    regressions[variant] = dict(summary=read(root / 'summary.json'), invocations=len(rows),
        totals=dict(totals), failures=failures, skips=skips,
        nonzero_invocations=[r for r in rows if r['returncode']],
        environment=dict(OMP_NUM_THREADS=2, OPENBLAS_NUM_THREADS=1, CUDA_VISIBLE_DEVICES='', HSOLVE_TEST_GPU_DEVICE=''),
        caveat='Counts include separately invoked thread/affinity tests and each MPI rank layout; not unique test identities.')

budget_rows = [r for r in runs if 'explicit_memory_budget_gb' in r]
budget_groups = {}
budget_pairs = []
for row in budget_rows:
    key = (row['case'], row['explicit_memory_budget_gb'])
    budget_groups.setdefault(key, {})[row['solver']] = row
for (case, budget), rows in sorted(budget_groups.items()):
    for control, candidate in [('hsolve-accepted', 'hsolve-packed'), ('hsolve-acceptednative', 'hsolve-packednative'), ('hsolve-packed', 'hsolve-capped'), ('hsolve-packednative', 'hsolve-cappednative')]:
        if control not in rows or candidate not in rows:
            continue
        a, b = rows[control], rows[candidate]
        def brief(row):
            peak = max(row.get('peak_rss_gib') or 0, (row.get('solver_peak_bytes') or 0) / 2**30)
            return dict(solver=row['solver'], valid=row['valid'], peak_gib=peak, peak_over_budget=peak > budget,
                        why=row.get('why'), error=row.get('error'), out=row['out'])
        budget_pairs.append(dict(case=case, budget_gib=budget, control=brief(a), candidate=brief(b),
            validity_regression=a['valid'] and not b['valid'], validity_improvement=b['valid'] and not a['valid']))

monitor_file = p / 'screen-monitor-result.json'
monitor = read(monitor_file) if monitor_file.exists() else None
qualified_cases = {}
performance = {}
if monitor and monitor.get('rows'):
    by_out = {r['out']: r for r in monitor['rows']}
    for name in sorted({r['case'] for r in monitor['rows']}):
        rows = [r for r in runs if tag(r) == 'p35-screen' and r['case'] == name]
        counts = collections.Counter(r['solver'] for r in rows)
        usable = len(counts) == 6 and all(n == 5 for n in counts.values()) and all(by_out[r['out']]['performance_usable'] for r in rows)
        qualified_cases[name] = usable
        if not usable:
            continue
        stats = {}
        for solver in sorted(counts):
            selected = [r for r in rows if r['solver'] == solver]
            values = [r['solver_s'] for r in selected]
            stats[solver] = dict(median_s=statistics.median(values), min_s=min(values), max_s=max(values),
                wall_median_s=statistics.median(r['wall_s'] for r in selected), valid=len(selected),
                max_eta=max(r['max_eta'] for r in selected),
                peak_gib=max(max(r.get('peak_rss_gib') or 0, (r.get('solver_peak_bytes') or 0)/2**30) for r in selected),
                phase_medians={key: statistics.median(r['phases'][key] for r in selected)
                               for key in selected[0].get('phases', {}) if all(r.get('phases', {}).get(key) is not None for r in selected)})
        ref = stats['slepc']['median_s']
        for solver in stats:
            stats[solver]['time_over_slepc'] = stats[solver]['median_s'] / ref
        performance[name] = stats

production = {str(repo/'build/release'/n): digest(repo/'build/release'/n)
              for n in ['hsolve', 'hsolve-mpi', 'libhsolve.a', 'libhsolve_blashook.so']}
production_source_sha256 = digest(repo/'src/driver/definite.cpp')
assert production_source_sha256 == 'f40ca695157d9334626b7928837716305c30439d257e0636ce9681e838d122d4'
build = read(p / 'packed-build-hashes.json')
assert production == build['production_before'] == build['production_after']
assert digest(p/'definite_packed.cpp') == build['source']
for name, sha in build['experimental'].items():
    assert digest(p/name) == sha
capped_build = read(p/'capped-build-hashes.json') if (p/'capped-build-hashes.json').exists() else None
if capped_build:
    assert production == capped_build['production_before'] == capped_build['production_after']
    assert digest(p/'definite_capped.cpp') == capped_build['source']
    for name, sha in capped_build['experimental'].items():
        assert digest(p/name) == sha
references = []
for row in runs:
    f = Path(row['out']) / 'report.json'
    if row['solver'] == 'slepc' and f.exists():
        report = read(f)
        references.append(dict(out=row['out'], scalar=report.get('petsc_scalar_type'), pc=report.get('factor_pc_type')))
assert all(r['scalar'] == 'complex128' and r['pc'] == 'lu' for r in references)

work_examples = []
for row in runs:
    if not row['case'].startswith('large-complex-'):
        continue
    root = Path(row['out'])
    events = root.parent/('events-'+root.name+'.jsonl')
    records = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    work_examples.append(dict(solver=row['solver'], out=row['out'], valid=row['valid'], max_eta=row.get('max_eta'),
        phases=row.get('phases'), events=[r for r in records if r.get('event') in ['lanczos', 'certificate', 'certificate_window_tightened', 'certificate_rerun_capped', 'corrected_deflation', 'done']]))

result = dict(round='P35', host='gpu02', goal_achieved=False, production_adopted=False,
    full_solve_attempts=len(runs), full_solve_valid=sum(bool(r['valid']) for r in runs),
    valid_completeness=dict(collections.Counter(r['completeness'] for r in runs if r['valid'])),
    groups=groups, regressions=regressions, budget_pairs=budget_pairs,
    budget_summary=dict(attempts=len(budget_rows), valid=sum(bool(r['valid']) for r in budget_rows),
        pairs=len(budget_pairs), validity_regressions=sum(r['validity_regression'] for r in budget_pairs),
        validity_improvements=sum(r['validity_improvement'] for r in budget_pairs),
        valid_over_budget=sum(r['valid'] and max(r.get('peak_rss_gib') or 0, (r.get('solver_peak_bytes') or 0)/2**30) > r['explicit_memory_budget_gb'] for r in budget_rows)),
    monitor=monitor, qualified_cases=qualified_cases, performance=performance,
    references=references, production_hashes=production, production_source_sha256=production_source_sha256, build=build, capped_build=capped_build, work_examples=work_examples,
    guards={name: read(p/name) for name in ['build-checks-guard.json', 'full-guard.json', 'budget-guard.json', 'main-guard.json', 'screen-guard.json', 'capped-guard.json', 'capped-validation-guard.json'] if (p/name).exists()},
    caveats=['Shared-core diagnostic timings are not qualified performance evidence.',
        'Explicit solver budgets guide planning; compare measured peak separately from validity and external 12 GiB guard.',
        'In-place column compaction retains vector capacity; the budget sweep cannot prove absence of all future allocation regressions.',
        'Photonic references are incomplete; consistent is not an independent complete-spectrum proof.',
        'P34 regression failures at OMP=8 and OpenBLAS=8 do not recur in this standard CMake OMP=2 and OpenBLAS=1 environment.',
        'Only tested SLEPc configurations are compared; these experiments cannot establish superiority over every open-source solver.'])
(p/'collected.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: result[k] for k in ['full_solve_attempts', 'full_solve_valid', 'budget_summary', 'qualified_cases']}, indent=2))
print(json.dumps({v: r['totals'] for v, r in regressions.items()}, indent=2))
