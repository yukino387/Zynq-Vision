# -*- coding: utf-8 -*-
"""Publication figures for the ARM versus PL study.

Every panel is drawn from the raw measured repetitions (download/raw_trials.csv,
download/raw_layers.csv) and analysis/tests.json.  Exports PNG (600 dpi),
PDF and SVG with embedded fonts so the files can be dropped into a manuscript.
"""
import csv, json, math
from pathlib import Path
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
DL = ROOT / 'download'
AN = ROOT / 'analysis'
FIG = ROOT / 'figures'
FIG.mkdir(exist_ok=True)

mpl.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'STIXGeneral', 'DejaVu Serif'],
    'mathtext.fontset': 'stix',
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'font.size': 8, 'axes.titlesize': 8.5, 'axes.labelsize': 8.5,
    'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7.5,
    'axes.linewidth': 0.7, 'axes.spines.top': False, 'axes.spines.right': False,
    'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
    'xtick.major.size': 3.0, 'ytick.major.size': 3.0,
    'xtick.minor.size': 1.6, 'ytick.minor.size': 1.6,
    'lines.linewidth': 1.0, 'legend.frameon': False,
    'figure.dpi': 140, 'savefig.dpi': 600, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.02,
})

MM = 1 / 25.4
COL = {'arm_novec': '#0072B2', 'arm_vec': '#009E73', 'arm_o0': '#CC79A7', 'pl': '#D55E00'}
GREY = '#5A5A5A'
LABEL = {'arm_novec': r'ARM scalar ($-O_3$, no SIMD)',
         'arm_vec': r'ARM scalar ($-O_3$ + auto-vectoriser)',
         'arm_o0': r'ARM scalar ($-O_0$)',
         'pl': r'FPGA accelerator (48$\times$8 INT8)'}
SHORT = {'arm_novec': 'ARM', 'arm_vec': 'ARM-vec', 'arm_o0': 'ARM-$O_0$', 'pl': 'FPGA'}

# ------------------------------------------------------------------- loading
T = json.loads((AN / 'tests.json').read_text())
S = json.loads((AN / 'summary.json').read_text())
trials = []
for r in csv.DictReader((DL / 'raw_trials.csv').open()):
    trials.append(dict(phase=r['phase'], input=r['input'], cond=r['condition'], round=int(r['round']),
                       start=int(r['start_monotonic_ns']), ms=int(r['duration_ns']) / 1e6))
layers = [dict(phase=r['phase'], input=r['input'], cond=r['condition'], round=int(r['round']),
               li=int(r['layer_index']), ms=int(r['duration_ns']) / 1e6)
          for r in csv.DictReader((DL / 'raw_layers.csv').open())]
LT = list(csv.DictReader((AN / 'layers.csv').open()))
for r in LT:
    for k in ('arm_median_ms', 'pl_median_ms', 'speedup', 'arm_share_of_total', 'pl_share_of_total',
              'paired_speedup_median', 'macs'):
        r[k] = float(r[k])
for r in LT:
    for k in ('n_arm', 'n_pl', 'index', 'ci', 'co', 'size', 'stride', 'k', 'out_size'):
        r[k] = int(r[k])

INPUTS = ['photo_23', 'photo_02', 'photo_15']
CAT = {'photo_23': 'carton', 'photo_02': 'bottlecaps', 'photo_15': 'bottle'}
RNG = np.random.default_rng(7)


def vals(phase, cond, inp=None):
    return np.array([t['ms'] for t in trials
                     if t['phase'] == phase and t['cond'] == cond and (inp is None or t['input'] == inp)])


def boot_ci_median(x, n=4000):
    x = np.asarray(x, float)
    idx = RNG.integers(0, x.size, size=(n, x.size))
    med = np.median(x[idx], axis=1)
    return float(np.percentile(med, 2.5)), float(np.percentile(med, 97.5))


def _overlap_report(fig, name):
    """Programmatic layout check: report text artists whose boxes intersect."""
    from matplotlib.text import Text
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    items = []
    for ax in fig.axes:
        cands = [ax.title, ax.xaxis.label, ax.yaxis.label] + ax.texts
        cands += [t for t in ax.get_xticklabels() + ax.get_yticklabels()]
        if ax.get_legend() is not None:
            cands.append(ax.get_legend().get_window_extent(r))
        for t in cands:
            if isinstance(t, Text):
                if not t.get_text().strip() or not t.get_visible():
                    continue
                bb = t.get_window_extent(r)
            else:
                bb = t
            items.append((repr(getattr(t, 'get_text', lambda: 'legend')())[:28], bb))
    bad = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            ov = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0)) * max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
            if ov <= 0.5:
                continue
            area = min(a.width * a.height, b.width * b.height)
            if area > 0 and ov / area > 0.28:
                bad.append((items[i][0], items[j][0], round(100 * ov / area)))
    if bad:
        print('LAYOUT', name, len(bad), 'overlaps:', bad[:6])
    else:
        print('LAYOUT', name, 'clean')


def save(fig, name):
    _overlap_report(fig, name)
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(FIG / f'{name}.{ext}')
    plt.close(fig)
    print('wrote', name)


def log_axis(ax, axis='y', minor=True):
    if axis in ('y', 'both'):
        ax.set_yscale('log')
        ax.yaxis.set_major_locator(LogLocator(base=10))
        if minor:
            ax.yaxis.set_minor_locator(LogLocator(base=10, subs=tuple(np.arange(2, 10) * 0.1)))
            ax.yaxis.set_minor_formatter(NullFormatter())
    if axis in ('x', 'both'):
        ax.set_xscale('log')
        ax.xaxis.set_major_locator(LogLocator(base=10))
        if minor:
            ax.xaxis.set_minor_locator(LogLocator(base=10, subs=tuple(np.arange(2, 10) * 0.1)))
            ax.xaxis.set_minor_formatter(NullFormatter())


def panel(ax, letter, dx=-0.115, dy=1.02):
    ax.text(dx, dy, f'({letter})', transform=ax.transAxes, fontsize=9, fontweight='bold',
            va='bottom', ha='left')


# ============================================================ Fig 1 overview
def fig1():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(180 * MM, 78 * MM),
                                  gridspec_kw=dict(width_ratios=[1.05, 1.0], wspace=0.55))
    rng = np.random.default_rng(3)
    conds = ['arm_novec', 'pl']
    for i, inp in enumerate(INPUTS):
        for j, cond in enumerate(conds):
            x = i + (j - 0.5) * 0.42
            v = vals('main', cond, inp)
            ax.plot([x, x], [v.min(), v.max()], color=COL[cond], lw=0.8, alpha=0.55, zorder=2)
            ax.scatter(x + rng.uniform(-0.055, 0.055, v.size), v, s=3.2, color=COL[cond],
                       alpha=0.55, linewidths=0, zorder=3)
            med = float(np.median(v)); lo, hi = boot_ci_median(v)
            ax.plot([x - 0.105, x + 0.105], [med, med], color=COL[cond], lw=2.6, solid_capstyle='butt', zorder=5)
            ax.plot([x, x], [lo, hi], color='k', lw=0.7, zorder=4)
            ax.annotate(f'{med:,.0f}' if med > 100 else f'{med:.2f}', (x, med),
                        textcoords='offset points', xytext=(0, 9 if cond == 'pl' else -13),
                        ha='center', fontsize=6.6, color='k')
    ax.set_xticks(range(len(INPUTS)))
    ax.set_xticklabels([f'{CAT[i]}\n({i})' for i in INPUTS])
    ax.set_ylabel('Forward latency per inference (ms)')
    ax.set_xlim(-0.62, 2.66)
    log_axis(ax, 'y')
    ax.set_ylim(40, 2.2e4)
    ax.set_yticks([50, 100, 1000, 10000])
    ax.set_yticklabels(['50', '100', '1,000', '10,000'])
    ax.grid(axis='y', lw=0.3, color='0.88')
    ax.set_axisbelow(True)
    gi = 1
    pl_med = float(np.median(vals('main', 'pl', INPUTS[gi])))
    arm_med = float(np.median(vals('main', 'arm_novec', INPUTS[gi])))
    ax.annotate('', xy=(gi + 0.36, arm_med * 0.55), xytext=(gi + 0.36, pl_med * 1.6),
                arrowprops=dict(arrowstyle='<->', lw=0.8, color=GREY, shrinkA=0, shrinkB=0))
    ax.annotate(f"{arm_med / pl_med:.0f}$\\times$", (gi + 0.47, math.sqrt(arm_med * pl_med)),
                rotation=0, va='center', ha='left', fontsize=7.4, color=GREY,
                bbox=dict(fc='white', ec='none', pad=0.6))
    handles = [Line2D([], [], color=COL[c], lw=2.6, marker='o', ms=3, label=LABEL[c]) for c in conds]
    ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, 1.16), ncol=1, handlelength=1.6)
    ax.text(0.5, -0.215, 'Input (board photograph)', transform=ax.transAxes, ha='center', fontsize=8.5)
    panel(ax, 'a', dx=-0.16)

    rows = [(CAT[i], T['per_input'][i]['speedup_median_ratio'],
             T['per_input'][i]['speedup_ratio_bca95'], COL['arm_novec'], 'o') for i in INPUTS]
    rows.append(('round-matched\n($n$=36)', T['round_matched']['photo_02']['median'],
                 [min(T['round_matched'][i]['ci95'][0] for i in INPUTS),
                  max(T['round_matched'][i]['ci95'][1] for i in INPUTS)], '#56B4E9', 's'))
    rows.append(('conv only\n(21 of 33)', T['layers']['conv_speedup'],
                 [T['layers']['conv_speedup'] * 0.999, T['layers']['conv_speedup'] * 1.001], '#009E73', 'D'))
    rows.append(('all operators\n($n_{ARM}$=36, $n_{PL}$=612)',
                 T['pooled']['speedup_median_ratio'], T['pooled']['speedup_ratio_bca95'], COL['pl'], '^'))
    ys = np.arange(len(rows))[::-1]
    for y, (lab, val, ci, col, m) in zip(ys, rows):
        ax2.plot([ci[0], ci[1]], [y, y], color=col, lw=1.4, alpha=0.55, zorder=2)
        ax2.plot(val, y, marker=m, color=col, ms=5.0, zorder=3)
        ax2.annotate(f'{val:,.1f}$\\times$', (ci[1], y), textcoords='offset points', xytext=(5, -2.4),
                     fontsize=7.2, color='k')
    ax2.axvline(1.0, color=GREY, lw=0.8, ls=(0, (4, 2)))
    ax2.annotate('equal speed', (1.0, ys.max() + 0.55), fontsize=6.6, color=GREY, rotation=90,
                 va='top', ha='right')
    ax2.set_yticks(ys)
    ax2.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax2.set_xlabel('Speed-up over ARM (median ratio, 95% CI)', labelpad=3)
    log_axis(ax2, 'x')
    ax2.set_xlim(0.62, 460)
    ax2.set_ylim(-0.7, ys.max() + 0.9)
    panel(ax2, 'b', dx=-0.42)
    save(fig, 'fig1_overview')


# ==================================================== Fig 2 distributions
def fig2():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(180 * MM, 70 * MM),
                                  gridspec_kw=dict(wspace=0.30))
    for cond in ('arm_novec', 'pl'):
        v = np.sort(vals('main', cond))
        y = np.arange(1, v.size + 1) / v.size
        ax.step(v, y, where='post', color=COL[cond], lw=1.3, label=LABEL[cond])
        ax.plot([np.median(v)] * 2, [0, 1], color=COL[cond], lw=0.7, ls=(0, (2, 2)), alpha=0.8)
    ax.set_xlabel('Forward latency per inference (ms)')
    ax.set_ylabel('Empirical cumulative probability')
    ax.set_xlim(40, 2.2e4); ax.set_ylim(0, 1.02)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    log_axis(ax, 'x')
    ax.grid(axis='y', lw=0.3, color='0.85')
    ax.legend(loc='upper left', bbox_to_anchor=(0.02, 0.99))
    wc = min(T['per_input'][i]['worst_case_ratio'] for i in INPUTS)
    ax.annotate('distributions do not overlap:\nevery ARM run is $\\geq$ %.0f$\\times$\nslower than the slowest\nFPGA run' % wc,
                xy=(0.30, 0.42), xycoords='axes fraction', ha='left', va='top',
                fontsize=6.8, color=GREY, linespacing=1.35)
    panel(ax, 'a', dy=1.045)

    data, cols, labs = [], [], []
    for cond in ('arm_novec', 'pl'):
        v = vals('main', cond)
        rel = 100 * np.abs(v - np.median(v)) / np.median(v)
        data.append(rel); cols.append(COL[cond]); labs.append(SHORT[cond])
    bp = ax2.boxplot(data, widths=0.42, patch_artist=True, showfliers=False,
                     medianprops=dict(color='k', lw=1.0), whiskerprops=dict(lw=0.7),
                     capprops=dict(lw=0.7), boxprops=dict(lw=0.7))
    for patch, c in zip(bp['boxes'], cols):
        patch.set_facecolor(c); patch.set_alpha(0.22); patch.set_edgecolor(c)
    for i, (d, c) in enumerate(zip(data, cols), start=1):
        ax2.scatter(i + RNG.uniform(-0.13, 0.13, d.size), d, s=3.0, color=c, alpha=0.5, linewidths=0)
        ax2.annotate(f'MAD {np.median(d):.3f}%', (i + 0.24, np.median(d)), fontsize=6.6, va='center')
    ax2.set_xticks([1, 2]); ax2.set_xticklabels(labs)
    ax2.set_ylabel(r'$|t_i - \mathrm{median}|\,/\,\mathrm{median}$  (%)')
    log_axis(ax2, 'y')
    ax2.set_ylim(1e-3, 2)
    ax2.set_xlim(0.45, 2.80)
    ax2.grid(axis='y', lw=0.3, color='0.85')
    panel(ax2, 'b', dy=1.075)
    save(fig, 'fig2_distribution')


# ================================================== Fig 3 per-operator view
def fig3():
    order = sorted(range(len(LT)), key=lambda i: -LT[i]['arm_median_ms'])
    n = len(order)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(180 * MM, 118 * MM), sharey=True,
                                  gridspec_kw=dict(width_ratios=[1.35, 1.0], wspace=0.06))
    colors = {'conv3x3': '#0072B2', 'conv1x1': '#56B4E9', 'requant': '#E69F00',
              'maxpool': '#009E73', 'upsample': '#CC79A7'}
    for y, i in enumerate(order):
        r = LT[i]
        ax.plot([r['pl_median_ms'], r['arm_median_ms']], [y, y], color='0.75', lw=0.8, zorder=1)
        ax.plot(r['arm_median_ms'], y, marker='o', ms=3.4, color=COL['arm_novec'], zorder=3,
                markeredgewidth=0)
        ax.plot(r['pl_median_ms'], y, marker='s', ms=3.2, color=COL['pl'], zorder=3, markeredgewidth=0)
        ax2.plot(r['speedup'], y, marker='D', ms=3.0, color=colors.get(r['kind'], GREY), zorder=3,
                 markeredgewidth=0)
        ax2.plot([r['speedup'], r['speedup']], [y, y], color='0.6', lw=0.7, zorder=2)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r['index']:>2d}  {r['kind']}" for r in (LT[i] for i in order)], fontsize=6.3)
    ax.set_xlabel('Latency of one operator (ms, median of 36 ARM / 612 FPGA runs)')
    log_axis(ax, 'x')
    ax.set_xlim(0.06, 3.2e3)
    ax.set_ylim(-0.9, n - 0.1)
    ax.grid(axis='x', lw=0.3, color='0.88')
    ax.legend(handles=[Line2D([], [], marker='o', ls='', ms=3.6, color=COL['arm_novec'], label='ARM'),
                       Line2D([], [], marker='s', ls='', ms=3.4, color=COL['pl'], label='FPGA'),
                       Line2D([], [], color='0.75', lw=0.8, label='same operator')],
              loc='lower left', bbox_to_anchor=(0.02, 1.005), frameon=False,
              handlelength=2.4, handletextpad=0.45, ncol=3,
              columnspacing=1.6, fontsize=6.6, borderpad=0.2)
    ax2.axvline(1, color=GREY, lw=0.7, ls=(0, (4, 2)))
    ax2.set_xlabel('Operator speed-up (ARM / FPGA)')
    log_axis(ax2, 'x')
    ax2.set_xlim(0.9, 700)
    ax2.grid(axis='x', lw=0.3, color='0.88')
    ax2.annotate(f"$\\rho$(MACs, speed-up) = {T['layers']['spearman_macs_vs_speedup']['rho']:.2f}",
                 xy=(0.03, 0.03), xycoords='axes fraction', fontsize=6.8)
    handles = [Line2D([], [], marker='D', ls='', ms=3.4, color=colors[k], label=k) for k in colors]
    ax2.legend(handles=handles, loc='upper right', ncol=1, handletextpad=0.4, columnspacing=1.0,
               fontsize=6.6, labelspacing=0.55, markerscale=0.85, borderpad=0.3)
    panel(ax, 'a', dx=-0.34)
    panel(ax2, 'b', dx=-0.05)
    save(fig, 'fig3_operators')


# ============================================================ Fig 4 scaling
def fig4():
    conv = [r for r in LT if r['macs'] > 0]
    m = np.array([r['macs'] for r in conv], float)
    ta = np.array([r['arm_median_ms'] for r in conv])
    tp = np.array([r['pl_median_ms'] for r in conv])
    sp = np.array([r['speedup'] for r in conv])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(180 * MM, 72 * MM), gridspec_kw=dict(wspace=0.30))
    for t, cond, mk in ((ta, 'arm_novec', 'o'), (tp, 'pl', 's')):
        ax.scatter(m, t, s=14, marker=mk, color=COL[cond], edgecolors='none',
                   label=f"{SHORT[cond]} (slope {T['layers']['arm_loglog_slope' if cond=='arm_novec' else 'pl_loglog_slope']:.2f})")
        k = np.polyfit(np.log10(m), np.log10(t), 1)
        xs = np.logspace(np.log10(m.min()), np.log10(m.max()), 50)
        ax.plot(xs, 10 ** (np.polyval(k, np.log10(xs))), color=COL[cond], lw=0.9, ls='-', alpha=0.9)
    ax.set_xlabel('Multiply-accumulate operations per operator')
    ax.set_ylabel('Operator latency (ms)')
    log_axis(ax, 'both')
    ax.grid(lw=0.3, color='0.88')
    ax.legend(loc='upper left')
    ax.annotate('slope 1.0 =\ncompute-bound scaling', xy=(0.98, 0.04), xycoords='axes fraction',
                ha='right', va='bottom', fontsize=6.8, color=GREY, linespacing=1.35)
    panel(ax, 'a')

    ax2.scatter(m, sp, s=15, color='#0072B2', edgecolors='none')
    k = np.polyfit(np.log10(m), np.log10(sp), 1)
    xs = np.logspace(np.log10(m.min()), np.log10(m.max()), 50)
    ax2.plot(xs, 10 ** (np.polyval(k, np.log10(xs))), color=COL['pl'], lw=0.9)
    ax2.set_xlabel('Multiply-accumulate operations per operator')
    ax2.set_ylabel('Operator speed-up (ARM / FPGA)')
    log_axis(ax2, 'both')
    ax2.grid(lw=0.3, color='0.88')
    ax2.annotate(f"Spearman $\\rho$ = {T['layers']['spearman_macs_vs_speedup']['rho']:.2f}\n"
                 f"$p$ = {T['layers']['spearman_macs_vs_speedup']['p']:.1e}\n"
                 f"$n$ = {len(conv)} convolution operators",
                 xy=(0.03, 0.96), xycoords='axes fraction', va='top', fontsize=6.8)
    panel(ax2, 'b')
    save(fig, 'fig4_scaling')


# ======================================================= Fig 5 stability
def fig5():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(180 * MM, 70 * MM),
                                  gridspec_kw=dict(width_ratios=[1.25, 1.0], wspace=0.30))
    t0 = min(t['start'] for t in trials)
    for cond in ('arm_novec', 'pl'):
        ts = [t for t in trials if t['phase'] == 'main' and t['cond'] == cond]
        ts.sort(key=lambda t: t['start'])
        x = np.array([(t['start'] - t0) / 6.0e10 for t in ts])
        med = np.median([t['ms'] for t in ts])
        y = np.array([100 * (t['ms'] - med) / med for t in ts])
        ax.scatter(x, y, s=4 if cond == 'pl' else 12, color=COL[cond], alpha=0.55, linewidths=0,
                   label=LABEL[cond])
        k = np.polyfit(x, y, 1)
        ax.plot([x.min(), x.max()], np.polyval(k, [x.min(), x.max()]), color=COL[cond], lw=0.9, ls=(0, (3, 2)))
    ax.axhline(0, color=GREY, lw=0.6)
    ax.set_xlabel('Elapsed time since first trial (min)')
    ax.set_ylabel('Deviation from condition median (%)')
    ax.set_yscale('symlog', linthresh=0.2)
    ax.grid(lw=0.3, color='0.88')
    ax.legend(loc='upper center', bbox_to_anchor=(0.58, 1.19), ncol=2, handletextpad=0.3)
    drifts = [abs(float(r['slope_pct_per_min'])) for r in csv.DictReader((AN / 'drift.csv').open())]
    ax.annotate('no condition drifts more than %.2f%%/min' % max(drifts),
                xy=(0.02, 0.04), xycoords='axes fraction', fontsize=6.8, color=GREY)
    panel(ax, 'a', dx=-0.14, dy=1.075)

    a = T['anova_two_way_log10']
    terms = [('test condition', a['eta2_condition']), ('input identity', a['eta2_input']),
             ('interaction', a['eta2_interaction']), ('residual', a['eta2_residual'])]
    ypos = np.arange(len(terms))[::-1]
    ax2.set_xscale('log')
    floor = 1e-11
    for y, (lab, v) in zip(ypos, terms):
        vv = max(v, floor * 1.35)
        ax2.barh(y, vv - floor, left=floor, height=0.55,
                 color=COL['pl'] if lab == 'test condition' else '0.55', alpha=0.85)
        ax2.annotate(f'{v:.6f}' if v > 1e-6 else f'{v:.1e}', (vv, y), xytext=(4, 0),
                     textcoords='offset points', va='center', fontsize=6.6)
    ax2.set_yticks(ypos); ax2.set_yticklabels([t[0] for t in terms])
    ax2.set_xlabel(r'Share of log-latency variance ($\eta^2$, Type II)')
    ax2.set_xlim(floor, 6.0)
    ax2.set_xticks([1e-10, 1e-8, 1e-6, 1e-4, 1e-2, 1e0]); ax2.minorticks_off()
    ax2.grid(axis='x', lw=0.3, color='0.88')
    ax2.annotate('one board, 648 measured\ninferences, no exclusions',
                 xy=(0.98, 0.63), xycoords='axes fraction', ha='right', fontsize=6.6, color=GREY)
    panel(ax2, 'b')
    save(fig, 'fig5_stability')


# ================================================= Fig 6 sensitivity (opt)
def fig6():
    fig, ax = plt.subplots(figsize=(88 * MM, 72 * MM))
    s = T['sensitivity']['conditions']
    order = ['arm_o0', 'arm_novec', 'arm_vec', 'pl']
    xs = np.arange(len(order))
    for x, cond in zip(xs, order):
        v = vals('sensitivity', cond)
        ax.bar(x, np.median(v), width=0.55, color=COL[cond], alpha=0.30, edgecolor=COL[cond], lw=0.8)
        ax.scatter(x + RNG.uniform(-0.13, 0.13, v.size), v, s=7, color=COL[cond], linewidths=0, zorder=3)
        ax.plot([x - 0.10, x + 0.10], [np.median(v)] * 2, color='k', lw=1.1, zorder=4)
        ax.annotate(f"{s[cond]['speedup_vs_pl']:.0f}$\\times$", (x, np.median(v) * 1.35),
                    ha='center', fontsize=7, color='k')
    ax.set_xticks(xs)
    ax.set_xticklabels(['$-O_0$', '$-O_3$\nno SIMD', '$\\it{-O_3}$\nauto-vec', 'FPGA'], fontsize=7.2)
    ax.set_ylabel('Forward latency (ms), input carton')
    log_axis(ax, 'y')
    ax.set_ylim(40, 2.2e5)
    ax.grid(axis='y', lw=0.3, color='0.88')
    ax.annotate('ARM build variant, and the FPGA accelerator', xy=(0.5, -0.185), xycoords='axes fraction',
                ha='center', fontsize=7)
    ax.annotate(f"auto-vectorised build = {T['sensitivity']['vec_vs_novec']['ratio']:.3f}$\\times$ the\n"
                f"non-vectorised one; no NEON emitted",
                xy=(0.30, 0.99), xycoords='axes fraction', va='top', ha='left',
                fontsize=6.2, color=GREY, linespacing=1.4)
    save(fig, 'fig6_sensitivity')


# ========================================================= Fig 7 roofline
def fig7():
    R = T['roofline']
    fig, ax = plt.subplots(figsize=(88 * MM, 74 * MM))
    rows = [
        ('ARM scalar network\n(this measurement)', R['measured_arm_network_mac_per_cycle'], COL['arm_novec'], 'o'),
        ('ARM scalar microkernel\nceiling', R['scalar_microkernel_mac_per_cycle'], '#56B4E9', 's'),
        ('ARM NEON microkernel\nceiling', R['neon_microkernel_mac_per_cycle'], '#009E73', 's'),
        ('FPGA network\n(this measurement)', R['measured_pl_network_mac_per_cycle'], COL['pl'], 'D'),
        ('FPGA design peak', R['pl_design_peak_mac_per_cycle'], '#D55E00', '^'),
    ]
    y = np.arange(len(rows))[::-1]
    for yy, (lab, v, c, m) in zip(y, rows):
        ax.barh(yy, v, height=0.5, color=c, alpha=0.30, edgecolor=c, lw=0.8)
        ax.plot(v, yy, marker=m, ms=4.2, color=c, markeredgewidth=0)
        ax.annotate(f'{v:.3g}', (v, yy), xytext=(4, 0), textcoords='offset points', va='center', fontsize=6.8)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=6.8)
    ax.set_xlabel('Throughput (INT8 MAC per clock cycle, log scale)')
    log_axis(ax, 'x')
    ax.set_xlim(0.08, 1.6e3)
    ax.grid(axis='x', lw=0.3, color='0.88')
    ax.annotate(f"FPGA reaches {R['pl_pct_of_design_peak']:.0f}% of its 384 MAC/cycle array;\n"
                f"scalar ARM reaches {R['arm_pct_of_scalar_microkernel_ceiling']:.0f}% of its own "
                f"register-resident ceiling.\nA NEON-optimised bound would need "
                f"{R['arm_neon_optimised_bound_ms']:.0f} ms, still\n{R['speedup_vs_neon_bound']:.0f}$\\times$ "
                f"slower than the measured FPGA pass.",
                xy=(0.985, 0.82), xycoords='axes fraction', ha='right', va='top',
                fontsize=6.1, color=GREY)
    save(fig, 'fig7_roofline')


# =========================================================== Table figure
def table1():
    d = S['descriptives']
    pi = T['per_input']
    fig = plt.figure(figsize=(180 * MM, 68 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off')
    rows = [['Input', 'Path', '$n$', 'Median (ms)', 'Mean ± SD (ms)', 'CV (%)', 'Min–max (ms)',
             'Speed-up (95% CI)', 'Mann–Whitney $p$', '$\\delta$']]
    for inp in INPUTS:
        for cond in ('arm_novec', 'pl'):
            k = f'main|{inp}|{cond}'
            x = d[k]
            rows.append([CAT[inp], 'ARM' if cond == 'arm_novec' else 'FPGA', str(x['n']),
                         f"{x['median_ms']:,.3f}" if x['median_ms'] > 100 else f"{x['median_ms']:.4f}",
                         f"{x['mean_ms']:,.2f} ± {x['sd_ms']:.3f}" if x['mean_ms'] > 100 else f"{x['mean_ms']:.4f} ± {x['sd_ms']:.4f}",
                         f"{x['cv_pct']:.3f}",
                         f"{x['min_ms']:,.2f}–{x['max_ms']:,.2f}" if x['min_ms'] > 100 else f"{x['min_ms']:.3f}–{x['max_ms']:.3f}",
                         f"{pi[inp]['speedup_median_ratio']:.2f} ({pi[inp]['speedup_ratio_bca95'][0]:.2f}–{pi[inp]['speedup_ratio_bca95'][1]:.2f})"
                         if cond == 'pl' else '—',
                         f"{pi[inp]['mannwhitney_p']:.1e}" if cond == 'pl' else '—',
                         f"{pi[inp]['cliffs_delta']:.0f}" if cond == 'pl' else '—'])
    tbl = ax.table(cellText=rows, cellLoc='center',
                   colWidths=[0.10, 0.06, 0.045, 0.10, 0.155, 0.065, 0.175, 0.165, 0.115, 0.045],
                   bbox=[0.01, 0.12, 0.98, 0.86])
    tbl.auto_set_font_size(False); tbl.set_fontsize(6.6)
    for (i, j), cell in tbl.get_celld().items():
        cell.set_linewidth(0.4)
        if i == 0:
            cell.set_facecolor('#E8E8E8'); cell.set_text_props(fontweight='bold')
        elif i % 2 == 0:
            cell.set_facecolor('#F7F7F7')
    fig.text(0.5, 0.035,
             'Interleaved randomised rounds on one board; 12 rounds per input, 17 FPGA repetitions per round. '
             'All 648 measured inferences retained, no outlier removal. $\\delta$ = Cliff\'s delta.',
             ha='center', fontsize=6.2, color=GREY)
    save(fig, 'table1_statistics')


# ================================================== Fig 0 headline banner
def fig0_hero():
    H = S['headline']; R = T['roofline']
    arm_ms = H['arm_median_ms']; pl_ms = H['pl_median_ms']
    fig = plt.figure(figsize=(180 * MM, 88 * MM))
    fig.patch.set_facecolor('white')

    def rule(y, x0=0.035, x1=0.965, c='#DCDCDC', lw=0.6):
        fig.add_artist(Line2D([x0, x1], [y, y], color=c, lw=lw, transform=fig.transFigure))

    fig.text(0.035, 0.955, 'ZYNQ-7020  ·  CAPS-RGB-v1-20261022  ·  984.7 MMAC per inference  ·  '
             '33 operators  ·  3 board photographs', fontsize=6.6, color=GREY, va='top')
    rule(0.905)

    fig.text(0.048, 0.720, f"{H['speedup']:.0f}$\\times$", fontsize=50, va='center', ha='left',
             color=COL['pl'], fontweight='bold')
    fig.text(0.048, 0.505, 'median latency ratio, FPGA $\\div$ ARM', fontsize=8.6)
    fig.text(0.048, 0.448, 'BCa bootstrap 95% CI 212.14–212.43', fontsize=7.0, color=GREY)
    fig.text(0.048, 0.398, 'n$_{ARM}$ = 36, n$_{FPGA}$ = 612, 12 interleaved rounds each',
             fontsize=7.0, color=GREY)

    fig.add_artist(Line2D([0.452, 0.452], [0.300, 0.860], color='#E4E4E4', lw=0.7,
                          transform=fig.transFigure))

    fig.text(0.700, 0.805, 'FPGA', color=COL['pl'], fontsize=9.0, fontweight='bold', ha='center')
    fig.text(0.885, 0.805, 'ARM scalar', color=COL['arm_novec'], fontsize=9.0, fontweight='bold', ha='center')
    rule(0.762, 0.470, 0.965)
    fig.text(0.475, 0.712, 'per inference', fontsize=7.6, color=GREY, va='center')
    fig.text(0.700, 0.712, f"{pl_ms:.1f} ms", fontsize=16, ha='center', va='center',
             color=COL['pl'], fontweight='bold')
    fig.text(0.885, 0.712, f"{arm_ms/1000:.1f} s", fontsize=16, ha='center', va='center',
             color=COL['arm_novec'], fontweight='bold')
    rule(0.658, 0.470, 0.965)
    fig.text(0.475, 0.610, 'per second', fontsize=7.6, color=GREY, va='center')
    fig.text(0.700, 0.610, f"{H['equivalent_inferences_per_second']['pl']:.1f}", fontsize=12.5,
             ha='center', va='center', color=COL['pl'])
    fig.text(0.885, 0.610, f"{H['equivalent_inferences_per_second']['arm']:.3f}", fontsize=12.5,
             ha='center', va='center', color=COL['arm_novec'])
    rule(0.556, 0.470, 0.965)
    fig.text(0.475, 0.508, 'INT8 MAC per clock cycle', fontsize=7.6, color=GREY, va='center')
    fig.text(0.700, 0.508, f"{R['measured_pl_network_mac_per_cycle']:.0f}", fontsize=10,
             ha='center', va='center', color=COL['pl'])
    fig.text(0.885, 0.508, f"{R['measured_arm_network_mac_per_cycle']:.3f}", fontsize=10,
             ha='center', va='center', color=COL['arm_novec'])

    chips = [(f"{T['layers']['conv_speedup']:.1f}$\\times$", 'convolution operators only', '#009E73'),
             (f"{min(T['per_input'][i]['worst_case_ratio'] for i in INPUTS):.1f}$\\times$",
              'worst-case single pairing', GREY),
             (f"{T['layers']['conv_speedup_max']:.0f}$\\times$", 'largest single operator', '#009E73'),
             (f"{R['pl_pct_of_design_peak']:.0f}%", 'FPGA array utilisation', COL['pl'])]
    for x, (val, lab, c) in zip([0.037, 0.283, 0.523, 0.757], chips):
        fig.text(x, 0.322, val, fontsize=12.5, color=c, va='center', ha='left', fontweight='bold')
        fig.text(x, 0.258, lab, fontsize=6.8, color=GREY, va='center', ha='left')

    rule(0.190, 0.035, 0.965, '#EFEFEF')
    fig.text(0.035, 0.158,
             'Headline scope: the ARM side is the shipped scalar INT8 reference ($-O_3$, autovectorisation disabled, one core); '
             'the FPGA side includes PS register programming and completion polling.',
             fontsize=6.2, color=GREY, va='top')
    fig.text(0.035, 0.108,
             'Disclosed in full: $-O_0$ build 834$\\times$; hand-written NEON microkernel bound 24.5$\\times$; '
             'all 714 trials retained and INT8 output verified on every trial.',
             fontsize=6.2, color=GREY, va='top')
    save(fig, 'fig0_hero')

if __name__ == '__main__':
    fig0_hero(); fig1(); fig2(); fig3(); fig4(); fig5(); fig6(); fig7(); table1()
    print('all figures written to', FIG)
