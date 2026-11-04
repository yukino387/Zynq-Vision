"""Summarize explicitly selected benchmark conditions; standard library only."""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def summarize(path, phase, baseline, candidate):
    if baseline == candidate:
        raise ValueError('baseline and candidate must differ')
    groups = defaultdict(lambda: defaultdict(list))
    hashes = defaultdict(set)
    rounds = defaultdict(lambda: defaultdict(int))
    required = {'phase', 'input', 'condition', 'round', 'duration_ns', 'output_sha256'}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('missing required CSV columns')
        for number, row in enumerate(reader, 2):
            if row['phase'] != phase or row['condition'] not in {baseline, candidate}:
                continue
            duration = int(row['duration_ns'])
            digest = row['output_sha256']
            if duration <= 0 or not row['input'] or not row['round'] or not re.fullmatch(r'[0-9a-fA-F]{64}', digest or ''):
                raise ValueError(f'invalid measurement at CSV line {number}')
            inp, cond = row['input'], row['condition']
            groups[inp][cond].append(duration / 1e6)
            hashes[inp].add(digest.lower())
            rounds[inp][(row['round'], cond)] += 1
    if not groups:
        raise ValueError('no selected measurements')
    output = []
    for inp in sorted(groups):
        conditions = groups[inp]
        if set(conditions) != {baseline, candidate} or len(hashes[inp]) != 1:
            raise ValueError(f'missing condition or inconsistent output SHA256 for {inp}')
        condition_rounds = {c: {r for r, k in rounds[inp] if k == c} for c in (baseline, candidate)}
        if condition_rounds[baseline] != condition_rounds[candidate]:
            raise ValueError(f'unpaired round identifiers for {inp}')
        stats = {}
        for c in (baseline, candidate):
            values = conditions[c]
            stats[c] = dict(n=len(values), median_ms=statistics.median(values),
                            min_ms=min(values), max_ms=max(values))
        output.append(dict(input=inp, conditions=stats,
                           ratio=stats[baseline]['median_ms']/stats[candidate]['median_ms'],
                           round_counts=[dict(round=r, condition=c, n=n)
                                         for (r, c), n in sorted(rounds[inp].items())]))
    pooled = {c: statistics.median([v for g in groups.values() for v in g[c]]) for c in (baseline, candidate)}
    equal = {c: statistics.mean(x['conditions'][c]['median_ms'] for x in output) for c in (baseline, candidate)}
    return dict(phase=phase, baseline=baseline, candidate=candidate, inputs=output,
                pooled_median_ms=pooled, pooled_ratio=pooled[baseline]/pooled[candidate],
                equal_input_mean_of_medians_ms=equal, equal_input_ratio=equal[baseline]/equal[candidate],
                output_hashes_consistent=True,
                limitations='Recorded hashes only; no hardware, timing-boundary or statistical-independence verification; no confidence interval.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--phase', required=True)
    p.add_argument('--baseline', required=True)
    p.add_argument('--candidate', required=True)
    a = p.parse_args()
    try:
        result = summarize(a.csv, a.phase, a.baseline, a.candidate)
    except (OSError, ValueError, KeyError, csv.Error) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
