# -*- coding: utf-8 -*-
"""Statistical analysis of the ARM versus PL latency campaign.

Reads the raw per-trial CSV produced on the board and writes:
  analysis/descriptives.csv   per-condition descriptive statistics
  analysis/layers.csv         per-operator ARM/PL latency and paired speedup
  analysis/drift.csv          time-drift regression per condition
  analysis/tests.json         hypothesis tests, effect sizes, confidence intervals
  analysis/summary.json       headline numbers and the roofline accounting
Everything is computed from the raw repetitions; no sample is removed.
"""
import csv, json, math, statistics as st
from pathlib import Path
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent
DL = ROOT / 'download'
OUT = ROOT / 'analysis'
OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(20261027)
Z = stats.norm

meta = json.loads((DL / 'run_meta.json').read_text())
MAC_TOTAL = meta['macs']
FCPU = 666666667.0                      # Hz, measured scaling_cur_freq
PL_PEAK_MAC_PER_CYCLE = 384.0           # 48x8 array, 192 DSP x 2 multipliers
PL_CLOCK = 125e6

# ---------------------------------------------------------------- load trials
trials = []
for r in csv.DictReader((DL / 'raw_trials.csv').open()):
    trials.append(dict(phase=r['phase'], input=r['input'], cond=r['condition'],
                       round=int(r['round']), task=int(r['task_index']),
                       start=int(r['start_monotonic_ns']), ms=int(r['duration_ns']) / 1e6,
                       sha=r['output_sha256']))
layers_raw = []
for r in csv.DictReader((DL / 'raw_layers.csv').open()):
    layers_raw.append((r['phase'], r['input'], r['condition'], int(r['round']),
                       int(r['layer_index']), int(r['duration_ns']) / 1e6))
cal = [dict(kernel=r['kernel'], n=int(r['n']), reps=int(r['reps']),
            ms=int(r['duration_ns']) / 1e6) for r in csv.DictReader((DL / 'raw_calibration.csv').open())]

cmds = json.loads((ROOT / 'command_layout.json').read_text())
ops = []
for i, c in enumerate(cmds):
    ci, co, size, stride, k = c[4], c[5], c[6], c[7], c[8]
    if k == 0:
        out_size, kind, macs = size * 2, 'upsample', 0
    elif k == 2:
        out_size, kind, macs = size // 2, 'maxpool', 0
    elif k in (1, 3):
        out_size = size // stride
        kind = 'conv1x1' if k == 1 else 'conv3x3'
        macs = co * out_size * out_size * ci * k * k
    else:
        out_size, kind, macs = size, 'requant', 0
    ops.append(dict(index=i, kind=kind, ci=ci, co=co, size=size, stride=stride, k=k,
                    out_size=out_size, macs=macs))
assert sum(o['macs'] for o in ops) == MAC_TOTAL, (sum(o['macs'] for o in ops), MAC_TOTAL)
assert len(ops) == 33

def sel(phase=None, inp=None, cond=None):
    out = trials
    if phase: out = [t for t in out if t['phase'] == phase]
    if inp:   out = [t for t in out if t['input'] == inp]
    if cond:  out = [t for t in out if t['cond'] == cond]
    return out

INPUTS = ['photo_23', 'photo_02', 'photo_15']
CAT = {'photo_23': 'carton', 'photo_02': 'caps', 'photo_15': 'bottle'}

# ------------------------------------------------------- integrity assertions
for ph in ('main', 'sensitivity'):
    for inp in INPUTS:
        shas = {t['sha'] for t in sel(ph, inp)}
        if shas:
            assert len(shas) == 1, ('INT8 output not identical within', ph, inp)
assert meta['truncated'] is False
assert meta['cpuFreqKHzStart'] == meta['cpuFreqKHzEnd'] == '666667'

# ------------------------------------------------------------- descriptives
def describe(v):
    v = np.asarray(sorted(v), dtype=float)
    n = len(v)
    q1, q3 = np.percentile(v, [25, 75])
    mean, sd = v.mean(), (v.std(ddof=1) if n > 1 else 0.0)
    return dict(n=n, mean_ms=mean, sd_ms=sd, cv_pct=100 * sd / mean if mean else None,
                median_ms=float(np.median(v)), iqr_ms=float(q3 - q1),
                min_ms=float(v.min()), max_ms=float(v.max()),
                p05_ms=float(np.percentile(v, 5)), p95_ms=float(np.percentile(v, 95)),
                skew=float(stats.skew(v)), kurtosis=float(stats.kurtosis(v)),
                range_ms=float(v.max() - v.min()))

desc_rows, desc_json = [], {}
for ph in ('main', 'sensitivity'):
    for inp in INPUTS:
        for cond in ('arm_novec', 'arm_vec', 'arm_o0', 'pl'):
            v = [t['ms'] for t in sel(ph, inp, cond)]
            if not v:
                continue
            d = describe(v)
            d.update(phase=ph, input=inp, condition=cond, category=CAT[inp])
            desc_rows.append(d)
            desc_json['%s|%s|%s' % (ph, inp, cond)] = d
with (OUT / 'descriptives.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['phase', 'input', 'category', 'condition', 'n', 'mean_ms',
                                      'sd_ms', 'cv_pct', 'median_ms', 'iqr_ms', 'min_ms', 'max_ms',
                                      'p05_ms', 'p95_ms', 'skew', 'kurtosis', 'range_ms'])
    w.writeheader(); [w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}) for r in desc_rows]

# ---------------------------------------------------------- Yuen trimmed mean
def yuen(a, b, tr=0.2):
    def part(x):
        x = np.sort(np.asarray(x, float)); n = len(x); g = int(math.floor(tr * n))
        xt = x[g:n - g]
        if g == 0:
            w = x.copy()
        else:
            w = np.concatenate([np.repeat(x[g], g), xt, np.repeat(x[n - g - 1], g)])
        return xt.mean(), w.var(ddof=1), len(xt)
    m1, v1, h1 = part(a); m2, v2, h2 = part(b)
    d1 = (h1 - 1) * v1 / (h1 * (h1 - 1)); d2 = (h2 - 1) * v2 / (h2 * (h2 - 1))
    t = (m1 - m2) / math.sqrt(d1 + d2)
    df = (d1 + d2) ** 2 / (d1 ** 2 / (h1 - 1) + d2 ** 2 / (h2 - 1))
    p = 2 * stats.t.sf(abs(t), df)
    se = math.sqrt(d1 + d2); crit = stats.t.ppf(0.975, df)
    return dict(trimmed_mean_arm=m1, trimmed_mean_pl=m2, t=float(t), df=float(df), p=float(p),
                diff_ms=m1 - m2, diff_ci95=[float(m1 - m2 - crit * se), float(m1 - m2 + crit * se)])

# ------------------------------------------------------------ bootstrap ratio
def boot_ratio(a, b, n=10000):
    a = np.asarray(a, float); b = np.asarray(b, float)
    res = stats.bootstrap((a, b), lambda x, y, axis=-1: np.median(x, axis=axis) / np.median(y, axis=axis),
                          n_resamples=n, method='BCa', vectorized=True, paired=False,
                          random_state=20261027)
    return float(res.confidence_interval.low), float(res.confidence_interval.high)

def perm_test(a, b, n=20000):
    a = np.asarray(a, float); b = np.asarray(b, float)
    obs = abs(np.median(a) - np.median(b))
    pool = np.concatenate([a, b]); hits = 0
    for _ in range(n):
        RNG.shuffle(pool)
        if abs(np.median(pool[:len(a)]) - np.median(pool[len(a):])) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)

def cliffs_delta(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    gt = (a[:, None] > b[None, :]).sum(); lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (a.size * b.size))

def hedges_g_log(a, b):
    la, lb = np.log10(a), np.log10(b)
    na, nb = la.size, lb.size
    sp = math.sqrt(((na - 1) * la.var(ddof=1) + (nb - 1) * lb.var(ddof=1)) / (na + nb - 2))
    d = (la.mean() - lb.mean()) / sp
    j = 1 - 3 / (4 * (na + nb) - 9)
    return float(d * j)

def power_gap(a, b, alpha=0.05, power=0.8):
    """Minimum detectable ratio at these sample sizes, and n needed for the observed effect."""
    la, lb = np.log10(a), np.log10(b)
    se = math.sqrt(la.var(ddof=1) / la.size + lb.var(ddof=1) / lb.size)
    mde_log = (Z.ppf(1 - alpha / 2) + Z.ppf(power)) * se
    obs = abs(la.mean() - lb.mean())
    # equal-n requirement for the observed effect
    s = math.sqrt((la.var(ddof=1) + lb.var(ddof=1)) / 2)
    n_req = 2 * ((Z.ppf(1 - alpha / 2) + Z.ppf(power)) * s / obs) ** 2
    return dict(mde_ratio_at_current_n=float(10 ** mde_log), observed_log10_gap=float(obs),
                n_per_group_required=float(math.ceil(n_req)),
                achieved_power=float(Z.cdf(obs / se - Z.ppf(1 - alpha / 2))))

def anova_two_way(factor_a, factor_b, values):
    """Type-II two-way ANOVA on an unbalanced design, fitted by least squares.
    SS for a term is the loss in residual sum of squares when that term is
    dropped from the model that keeps every other term."""
    y = np.asarray(values, float)
    A = np.asarray(factor_a); B = np.asarray(factor_b)
    la, lb = sorted(set(A)), sorted(set(B))
    def dum(v, levels):
        return np.column_stack([(v == l).astype(float) for l in levels[1:]])
    Xa, Xb = dum(A, la), dum(B, lb)
    Xint = np.column_stack([Xa[:, i] * Xb[:, j] for i in range(Xa.shape[1]) for j in range(Xb.shape[1])]) \
        if Xa.shape[1] and Xb.shape[1] else np.zeros((len(y), 0))
    one = np.ones((len(y), 1))
    def rss(X):
        if X.shape[1] == 0:
            r = y - y.mean(); return float(r @ r)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ beta
        return float(r @ r)
    full = rss(np.column_stack([one, Xa, Xb, Xint]))
    both = rss(np.column_stack([one, Xa, Xb]))
    ss_a = rss(np.column_stack([one, Xb])) - both
    ss_b = rss(np.column_stack([one, Xa])) - both
    ss_ab = both - full
    sst = float(((y - y.mean()) ** 2).sum())
    dfa, dfb = len(la) - 1, len(lb) - 1
    dfab = dfa * dfb
    dfe = len(y) - len(la) * len(lb)
    mse = full / dfe
    return {'SS_condition': ss_a, 'SS_input': ss_b, 'SS_interaction': ss_ab,
            'SS_residual': full, 'SS_total': sst,
            'F_condition': ss_a / dfa / mse, 'p_condition': float(stats.f.sf(ss_a / dfa / mse, dfa, dfe)),
            'F_input': ss_b / dfb / mse, 'p_input': float(stats.f.sf(ss_b / dfb / mse, dfb, dfe)),
            'F_interaction': ss_ab / dfab / mse,
            'p_interaction': float(stats.f.sf(ss_ab / dfab / mse, dfab, dfe)),
            'eta2_condition': ss_a / sst, 'eta2_input': ss_b / sst,
            'eta2_interaction': ss_ab / sst, 'eta2_residual': full / sst,
            'df': [dfa, dfb, dfab, dfe]}

# --------------------------------------------------------------- main tests
tests = {'design': {'phase': 'main', 'repetitions_per_input': {'arm_novec': 12, 'pl': 204},
                    'inputs': INPUTS, 'interleaved_rounds': 12, 'seed': meta['seed'],
                    'budget_truncated': meta['truncated']},
         'per_input': {}, 'pooled': {}}

for inp in INPUTS:
    a = np.array([t['ms'] for t in sel('main', inp, 'arm_novec')])
    b = np.array([t['ms'] for t in sel('main', inp, 'pl')])
    la, lb = np.log10(a), np.log10(b)
    sw_a = stats.shapiro(la); sw_b = stats.shapiro(lb)
    bf = stats.levene(la, lb, center='median')
    welch = stats.ttest_ind(la, lb, equal_var=False)
    mwu = stats.mannwhitneyu(a, b, alternative='two-sided')
    lo, hi = boot_ratio(a, b)
    d = {
        'n': {'arm_novec': int(a.size), 'pl': int(b.size)},
        'median_arm_ms': float(np.median(a)), 'median_pl_ms': float(np.median(b)),
        'mean_arm_ms': float(a.mean()), 'mean_pl_ms': float(b.mean()),
        'sd_arm_ms': float(a.std(ddof=1)), 'sd_pl_ms': float(b.std(ddof=1)),
        'cv_arm_pct': float(100 * a.std(ddof=1) / a.mean()),
        'cv_pl_pct': float(100 * b.std(ddof=1) / b.mean()),
        'speedup_median_ratio': float(np.median(a) / np.median(b)),
        'speedup_ratio_bca95': [lo, hi],
        'speedup_mean_ratio': float(a.mean() / b.mean()),
        'worst_case_ratio': float(a.min() / b.max()),
        'best_case_ratio': float(a.max() / b.min()),
        'shapiro_p_arm_log': float(sw_a.pvalue), 'shapiro_p_pl_log': float(sw_b.pvalue),
        'brown_forsythe_p': float(bf.pvalue),
        'welch_log_t': float(welch.statistic), 'welch_log_p': float(welch.pvalue),
        'mannwhitney_u': float(mwu.statistic), 'mannwhitney_p': float(mwu.pvalue),
        'permutation_p': perm_test(a, b, 20000),
        'yuen20': yuen(a, b),
        'hedges_g_log10': hedges_g_log(a, b),
        'cliffs_delta': cliffs_delta(a, b),
        'prob_superiority': 1.0 if a.min() > b.max() else float(
            np.mean((a[:, None] > b[None, :]) + 0.5 * (a[:, None] == b[None, :]))),
        'n_overlap_pairs_lower_than_arm_min': int((b >= a.min()).sum()),
        'power': power_gap(a, b),
        'gmac_per_s': {'arm_novec': MAC_TOTAL / (np.median(a) / 1e3) / 1e9 * 1e-3 * 1e3,
                       'pl': MAC_TOTAL / (np.median(b) / 1e3) / 1e9 * 1e-3 * 1e3}}
    # GMAC/s = MAC / (ms/1000) / 1e9
    d['gmac_per_s'] = {'arm_novec': MAC_TOTAL / (np.median(a) * 1e-3) / 1e9,
                       'pl': MAC_TOTAL / (np.median(b) * 1e-3) / 1e9}
    d['mac_per_cycle'] = {'arm_novec': d['gmac_per_s']['arm_novec'] * 1e9 / FCPU,
                          'pl': d['gmac_per_s']['pl'] * 1e9 / PL_CLOCK * 1}
    d['pl_pct_of_design_peak'] = 100 * d['gmac_per_s']['pl'] * 1e9 / (PL_PEAK_MAC_PER_CYCLE * PL_CLOCK)
    tests['per_input'][inp] = d

a_all = np.array([t['ms'] for t in sel('main', None, 'arm_novec')])
b_all = np.array([t['ms'] for t in sel('main', None, 'pl')])
lo, hi = boot_ratio(a_all, b_all)
tests['pooled'] = {
    'n': {'arm_novec': int(a_all.size), 'pl': int(b_all.size)},
    'median_arm_ms': float(np.median(a_all)), 'median_pl_ms': float(np.median(b_all)),
    'speedup_median_ratio': float(np.median(a_all) / np.median(b_all)),
    'speedup_ratio_bca95': [lo, hi],
    'median_of_per_input_medians': {
        'arm_novec': float(np.median([tests['per_input'][i]['median_arm_ms'] for i in INPUTS])),
        'pl': float(np.median([tests['per_input'][i]['median_pl_ms'] for i in INPUTS]))},
    'mannwhitney_p': float(stats.mannwhitneyu(a_all, b_all).pvalue),
    'welch_log_p': float(stats.ttest_ind(np.log10(a_all), np.log10(b_all), equal_var=False).pvalue),
    'permutation_p': perm_test(a_all, b_all, 20000),
    'cliffs_delta': cliffs_delta(a_all, b_all),
    'hedges_g_log10': hedges_g_log(a_all, b_all),
}
tests['pooled']['median_of_per_input_medians']['ratio'] = (
    tests['pooled']['median_of_per_input_medians']['arm_novec'] /
    tests['pooled']['median_of_per_input_medians']['pl'])

# round-matched ratios (drift-free pairing): ARM trial in round r against the
# median of the PL trials measured in the same round
matched = {}
for inp in INPUTS:
    by_round = {}
    for t in sel('main', inp):
        by_round.setdefault(t['round'], []).append(t)
    ratios = []
    for rnd, ts in sorted(by_round.items()):
        arm = [t['ms'] for t in ts if t['cond'] == 'arm_novec']
        pl = [t['ms'] for t in ts if t['cond'] == 'pl']
        if arm and pl:
            ratios.append(arm[0] / float(np.median(pl)))
    matched[inp] = dict(n=len(ratios), median=float(np.median(ratios)),
                        ci95=[float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))],
                        min=float(min(ratios)), max=float(max(ratios)))
tests['round_matched'] = matched

# two-way ANOVA over the main phase, log10 latency
fa, fb, vals = [], [], []
for t in sel('main'):
    if t['cond'] in ('arm_novec', 'pl'):
        fa.append(t['cond']); fb.append(t['input']); vals.append(math.log10(t['ms']))
tests['anova_two_way_log10'] = anova_two_way(fa, fb, vals)

# ---------------------------------------------------------------- drift tests
drift_rows, drift = [], {}
t0 = min(t['start'] for t in trials)
for ph in ('main', 'sensitivity'):
    for inp in INPUTS:
        for cond in ('arm_novec', 'arm_vec', 'arm_o0', 'pl'):
            ts = [t for t in sel(ph, inp, cond)]
            if len(ts) < 4:
                continue
            x = np.array([(t['start'] - t0) / 1e9 for t in ts])
            y = np.array([math.log10(t['ms']) for t in ts])
            lr = stats.linregress(x, y)
            slope_rel_pct_per_min = (10 ** (lr.slope * 60) - 1) * 100
            row = dict(phase=ph, input=inp, condition=cond, n=len(ts),
                       span_s=float(x.max() - x.min()),
                       slope_log10_per_s=float(lr.slope),
                       slope_pct_per_min=float(slope_rel_pct_per_min),
                       slope_ci95=[float(lr.slope - 1.96 * lr.stderr), float(lr.slope + 1.96 * lr.stderr)],
                       p=float(lr.pvalue), r2=float(lr.rvalue ** 2))
            drift_rows.append(row)
            drift['%s|%s|%s' % (ph, inp, cond)] = row
with (OUT / 'drift.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['phase', 'input', 'condition', 'n', 'span_s', 'slope_log10_per_s',
                                      'slope_pct_per_min', 'p', 'r2'], extrasaction='ignore')
    w.writeheader(); [w.writerow({k: (round(v, 8) if isinstance(v, float) else v) for k, v in r.items()}) for r in drift_rows]

# ------------------------------------------------------------- per-operator
def layer_series(phase, inp, cond):
    out = {}
    for ph, ip, cd, rnd, li, ms in layers_raw:
        if ph != phase or (inp and ip != inp) or cd != cond:
            continue
        out.setdefault((ip, rnd, li), []).append(ms)
    return out

arm_l = layer_series('main', None, 'arm_novec')
pl_l = layer_series('main', None, 'pl')
layer_rows = []
for op in ops:
    i = op['index']
    a = np.array([v[0] for (ip, rnd, li), v in arm_l.items() if li == i])
    b = np.array([v[0] for (ip, rnd, li), v in pl_l.items() if li == i])
    paired = []
    for (ip, rnd, li), v in arm_l.items():
        if li != i:
            continue
        key = (ip, rnd, i)
        if key in pl_l:
            paired.append(v[0] / pl_l[key][0])
    paired = np.array(paired)
    row = dict(index=i, kind=op['kind'], ci=op['ci'], co=op['co'], size=op['size'],
               stride=op['stride'], k=op['k'], out_size=op['out_size'], macs=op['macs'],
               n_arm=int(a.size), n_pl=int(b.size),
               arm_median_ms=float(np.median(a)), pl_median_ms=float(np.median(b)),
               arm_min_ms=float(a.min()), arm_max_ms=float(a.max()),
               pl_min_ms=float(b.min()), pl_max_ms=float(b.max()),
               speedup=float(np.median(a) / np.median(b)),
               paired_speedup_median=float(np.median(paired)),
               paired_speedup_ci95=[float(np.percentile(paired, 2.5)), float(np.percentile(paired, 97.5))],
               arm_share_of_total=float(np.median(a) / np.median([t['ms'] for t in sel('main', None, 'arm_novec')])),
               pl_share_of_total=float(np.median(b) / np.median([t['ms'] for t in sel('main', None, 'pl')])))
    if op['macs']:
        row['arm_effective_gops'] = op['macs'] / (np.median(a) * 1e-3) / 1e9
        row['pl_effective_gops'] = op['macs'] / (np.median(b) * 1e-3) / 1e9
    layer_rows.append(row)
with (OUT / 'layers.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['index', 'kind', 'ci', 'co', 'size', 'stride', 'k', 'out_size', 'macs',
                                      'n_arm', 'n_pl', 'arm_median_ms', 'pl_median_ms', 'arm_min_ms', 'arm_max_ms',
                                      'pl_min_ms', 'pl_max_ms', 'speedup', 'paired_speedup_median',
                                      'arm_share_of_total', 'pl_share_of_total', 'arm_effective_gops',
                                      'pl_effective_gops'], extrasaction='ignore')
    w.writeheader(); [w.writerow({k: (round(v, 8) if isinstance(v, float) else v) for k, v in r.items()}) for r in layer_rows]

conv = [r for r in layer_rows if r['macs'] > 0]
arm_conv_ms = sum(r['arm_median_ms'] for r in conv)
pl_conv_ms = sum(r['pl_median_ms'] for r in conv)
sp = np.array([r['paired_speedup_median'] for r in conv])
w_stat = stats.wilcoxon(sp - 1.0) if len(sp) > 5 else None
x = np.log10([r['macs'] for r in conv]); y1 = np.log10([r['arm_median_ms'] for r in conv])
y2 = np.log10([r['pl_median_ms'] for r in conv]); y3 = np.log10([r['speedup'] for r in conv])
r1 = stats.linregress(x, y1); r2 = stats.linregress(x, y2)
rho_arm, p_arm = stats.spearmanr([r['macs'] for r in conv], [r['arm_median_ms'] for r in conv])
rho_pl, p_pl = stats.spearmanr([r['macs'] for r in conv], [r['pl_median_ms'] for r in conv])
rho_sp, p_sp = stats.spearmanr([r['macs'] for r in conv], [r['speedup'] for r in conv])
layer_stats = {
    'conv_commands': len(conv),
    'conv_arm_median_sum_ms': arm_conv_ms, 'conv_pl_median_sum_ms': pl_conv_ms,
    'conv_speedup': arm_conv_ms / pl_conv_ms,
    'all_arm_median_sum_ms': sum(r['arm_median_ms'] for r in layer_rows),
    'all_pl_median_sum_ms': sum(r['pl_median_ms'] for r in layer_rows),
    'conv_speedup_min': float(min(r['speedup'] for r in conv)),
    'conv_speedup_max': float(max(r['speedup'] for r in conv)),
    'wilcoxon_speedup_gt1': {'statistic': float(w_stat.statistic), 'p': float(w_stat.pvalue)} if w_stat else None,
    'arm_loglog_slope': float(r1.slope), 'arm_loglog_r2': float(r1.rvalue ** 2),
    'pl_loglog_slope': float(r2.slope), 'pl_loglog_r2': float(r2.rvalue ** 2),
    'spearman_macs_vs_arm': {'rho': float(rho_arm), 'p': float(p_arm)},
    'spearman_macs_vs_pl': {'rho': float(rho_pl), 'p': float(p_pl)},
    'spearman_macs_vs_speedup': {'rho': float(rho_sp), 'p': float(p_sp)},
    'arm_mac_per_cycle_conv': (MAC_TOTAL / (arm_conv_ms * 1e-3)) / FCPU,
    'pl_mac_per_cycle_conv': (MAC_TOTAL / (pl_conv_ms * 1e-3)) / PL_CLOCK,
    'pl_pct_of_peak_conv': 100 * (MAC_TOTAL / (pl_conv_ms * 1e-3)) / (PL_PEAK_MAC_PER_CYCLE * PL_CLOCK),
}
tests['layers'] = layer_stats

# ------------------------------------------------------- repeatability test
rep = {}
for inp in INPUTS:
    a = np.array([t['ms'] for t in sel('main', inp, 'arm_novec')])
    b = np.array([t['ms'] for t in sel('main', inp, 'pl')])
    da = np.abs(a - np.median(a)) / np.median(a)
    db = np.abs(b - np.median(b)) / np.median(b)
    rep[inp] = {'cv_ratio_arm_over_pl': float((a.std(ddof=1) / a.mean()) / (b.std(ddof=1) / b.mean())),
                'mad_ratio_arm_over_pl': float(np.median(da) / np.median(db)),
                'fligner_p': float(stats.fligner(da, db).pvalue),
                'relative_span_arm_pct': float(100 * (a.max() - a.min()) / np.median(a)),
                'relative_span_pl_pct': float(100 * (b.max() - b.min()) / np.median(b))}
tests['repeatability'] = rep

# ------------------------------------------------------------ sensitivity set
sens = {}
for cond in ('arm_o0', 'arm_novec', 'arm_vec', 'pl'):
    v = np.array([t['ms'] for t in sel('sensitivity', 'photo_23', cond)])
    sens[cond] = dict(n=int(v.size), median_ms=float(np.median(v)), mean_ms=float(v.mean()),
                      sd_ms=float(v.std(ddof=1)), cv_pct=float(100 * v.std(ddof=1) / v.mean()),
                      min_ms=float(v.min()), max_ms=float(v.max()))
base = sens['pl']['median_ms']
for k in sens:
    sens[k]['speedup_vs_pl'] = sens[k]['median_ms'] / base
tk = stats.tukey_hsd(*[np.log10([t['ms'] for t in sel('sensitivity', 'photo_23', c)])
                       for c in ('arm_o0', 'arm_novec', 'arm_vec', 'pl')])
order = ['arm_o0', 'arm_novec', 'arm_vec', 'pl']
tests['sensitivity'] = {
    'input': 'photo_23', 'conditions': sens,
    'tukey_log10_pvalues': {('%s|%s' % (order[i], order[j])): float(tk.pvalue[i][j])
                            for i in range(4) for j in range(4) if i < j},
}
# autovectorisation control: -O3 with vectorisation vs -O3 without
vec_a = np.array([t['ms'] for t in sel('sensitivity', 'photo_23', 'arm_vec')])
nov_a = np.array([t['ms'] for t in sel('sensitivity', 'photo_23', 'arm_novec')])
tests['sensitivity']['vec_vs_novec'] = {
    'ratio': float(np.median(vec_a) / np.median(nov_a)),
    'welch_p_log10': float(stats.ttest_ind(np.log10(vec_a), np.log10(nov_a), equal_var=False).pvalue),
    'note': 'GCC 13.4 at -O3 -mcpu=cortex-a9 -mfpu=neon emitted no NEON instructions for the scalar convolution; the two builds differ only in code layout.'}

# ------------------------------------------------------------------ roofline
cal_s = np.array([c['ms'] for c in cal if c['kernel'] == 'scalar'])
cal_n = np.array([c['ms'] for c in cal if c['kernel'] == 'neon'])
macs_s = [c['n'] * c['reps'] for c in cal if c['kernel'] == 'scalar'][0]
macs_n = [c['n'] * c['reps'] for c in cal if c['kernel'] == 'neon'][0]
scalar_mac_per_cycle = (macs_s / (np.median(cal_s) * 1e-3)) / FCPU
neon_mac_per_cycle = (macs_n / (np.median(cal_n) * 1e-3)) / FCPU
roofline = {
    'calibration_n': int(cal[0]['n']), 'calibration_reps': {'scalar': 300, 'neon': 3000}, 'macs_per_round': {'scalar': macs_s, 'neon': macs_n},
    'scalar_microkernel_mac_per_cycle': float(scalar_mac_per_cycle),
    'neon_microkernel_mac_per_cycle': float(neon_mac_per_cycle),
    'neon_over_scalar': float(neon_mac_per_cycle / scalar_mac_per_cycle),
    'measured_arm_network_mac_per_cycle': layer_stats['arm_mac_per_cycle_conv'],
    'measured_pl_network_mac_per_cycle': layer_stats['pl_mac_per_cycle_conv'],
    'pl_design_peak_mac_per_cycle': PL_PEAK_MAC_PER_CYCLE,
    'pl_pct_of_design_peak': layer_stats['pl_pct_of_peak_conv'],
    'arm_pct_of_scalar_microkernel_ceiling': 100 * layer_stats['arm_mac_per_cycle_conv'] / scalar_mac_per_cycle,
    'arm_neon_optimised_bound_ms': float(MAC_TOTAL / (neon_mac_per_cycle * FCPU) * 1e3),
    'pl_measured_ms': layer_stats['conv_pl_median_sum_ms'],
    'speedup_vs_neon_bound': float((MAC_TOTAL / (neon_mac_per_cycle * FCPU) * 1e3) / layer_stats['conv_pl_median_sum_ms']),
}
tests['roofline'] = roofline

# ------------------------------------------------------------------- summary
summary = {
    'headline': {
        'scope': 'main phase, 33 operators, 3 inputs, 12 interleaved rounds per input',
        'arm_condition': 'arm_novec: the shipped scalar INT8 reference, -O3, autovectorisation disabled, single core (CPU1), no NEON',
        'pl_condition': 'pl: 48x8 INT8 accelerator, deployed bitstream, PS display and capture stopped, timing includes PS register programming and completion polling',
        'arm_median_ms': tests['pooled']['median_of_per_input_medians']['arm_novec'],
        'pl_median_ms': tests['pooled']['median_of_per_input_medians']['pl'],
        'speedup': tests['pooled']['median_of_per_input_medians']['ratio'],
        'speedup_bca95': tests['pooled']['speedup_ratio_bca95'],
        'equivalent_inferences_per_second': {'arm': 1000 / tests['pooled']['median_of_per_input_medians']['arm_novec'],
                                             'pl': 1000 / tests['pooled']['median_of_per_input_medians']['pl']},
    },
    'conv_only': {'arm_ms': arm_conv_ms, 'pl_ms': pl_conv_ms, 'speedup': arm_conv_ms / pl_conv_ms},
    'integrity': {'samples': len(trials), 'layer_samples': len(layers_raw),
                  'int8_output_bytes': meta['outputBytes'], 'identical_outputs_all_trials': True,
                  'mismatches': 0, 'truncated': meta['truncated'],
                  'exclusions': 'none; predefined warm-ups are outside the measured arrays'},
    'environment': {k: meta.get(k) for k in ('cpuFreqKHzStart', 'cpuFreqKHzEnd', 'modelSha256',
                                              'modelVersion', 'inputChannels', 'macs', 'seed')},
    'descriptives': desc_json,
    'roofline': roofline,
}
tests['summary'] = summary
(OUT / 'tests.json').write_text(json.dumps(tests, indent=2, ensure_ascii=False))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))

print('== headline ==')
h = summary['headline']
print('ARM %s ms  PL %s ms  speedup %.2fx  95%% CI [%.2f, %.2f]' % (
    f"{h['arm_median_ms']:.3f}", f"{h['pl_median_ms']:.4f}", h['speedup'], *h['speedup_bca95']))
print('conv-only %.2fx | per-input:' % summary['conv_only']['speedup'],
      {k: round(v['speedup_median_ratio'], 2) for k, v in tests['per_input'].items()})
print('tests pooled:', {k: tests['pooled'][k] for k in ('mannwhitney_p', 'welch_log_p', 'permutation_p', 'cliffs_delta')})
print('per-input CI:', {k: [round(x, 2) for x in v['speedup_ratio_bca95']] for k, v in tests['per_input'].items()})
print('ANOVA eta2:', {k: round(v, 6) for k, v in tests['anova_two_way_log10'].items() if k.startswith('eta2')})
print('power:', {k: tests['per_input']['photo_23']['power'][k] for k in ('mde_ratio_at_current_n', 'n_per_group_required', 'achieved_power')})
print('repeatability:', {k: {kk: round(vv,3) for kk,vv in v.items()} for k,v in tests['repeatability'].items()})
print('layers:', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in layer_stats.items() if not isinstance(v, dict)})
print('roofline:', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in roofline.items()})
print('sensitivity speedups:', {k: round(v['speedup_vs_pl'], 2) for k, v in sens.items()})
print('vec vs novec ratio:', round(tests['sensitivity']['vec_vs_novec']['ratio'], 5),
      'p=', tests['sensitivity']['vec_vs_novec']['welch_p_log10'])
print('drift |slope| max %/min:', round(max(abs(r['slope_pct_per_min']) for r in drift_rows), 4),
      'min p:', round(min(r['p'] for r in drift_rows), 4))
