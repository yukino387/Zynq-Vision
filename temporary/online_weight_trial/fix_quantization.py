from pathlib import Path
p=Path('packages/shared/src/index.ts');s=p.read_text(encoding='utf-8');old='  return keys.filter((k) => canonical(expected[k]) !== canonical(candidate[k]));';new='''  return keys.filter((k) => {
    if (k !== "quantization") return canonical(expected[k]) !== canonical(candidate[k]);
    const a = expected.quantization, b = candidate.quantization;
    // JSON storage may round a double by a few ULPs. Hardware scales still
    // must match to floating-point precision, not an application tolerance.
    const sameScale = (x: number, y: number) =>
      x === y || Math.abs(x - y) <= 4 * Number.EPSILON * Math.max(Math.abs(x), Math.abs(y));
    return a.scheme !== b.scheme || a.inputZeroPoint !== b.inputZeroPoint ||
      !sameScale(a.inputScale, b.inputScale) || a.outputScales.length !== b.outputScales.length ||
      a.outputScales.some((scale, i) => !sameScale(scale, b.outputScales[i]!));
  });''';assert old in s;s=s.replace(old,new,1);p.write_bytes(s.encode())
