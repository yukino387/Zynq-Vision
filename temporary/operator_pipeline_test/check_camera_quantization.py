from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
source = (root / 'camera/camera_input.cpp').read_text(encoding='utf-8')
body = source[source.index('void camera_to_input('):]
expressions = re.findall(r'input\[[^\]]+\]\s*=\s*([^;]+);', body)
assert len(expressions) == 3
for pixel in range(65536):
    r5, g6, b5 = pixel >> 11, (pixel >> 5) & 63, pixel & 31
    values = dict(r=(r5 << 3) | (r5 >> 2), g=(g6 << 2) | (g6 >> 4), b=(b5 << 3) | (b5 >> 2))
    for channel, expression in zip(('r', 'g', 'b'), expressions):
        actual = eval(expression, {'__builtins__': {}}, values)
        expected = (values[channel] * 512 + 127) // 255
        assert actual == expected, (pixel, channel, actual, expected)
print('PASS: all 65536 RGB565 pixels, all 3 CHW channels match original quantization exactly')
build = Path(__file__).resolve().parent / 'build'
build.mkdir(exist_ok=True)
prefix = 'typedef unsigned short uint16_t; typedef short data_t; enum {CAMERA_PIXELS=416*416};\n'
old = body
for channel, expression in zip(('r', 'g', 'b'), expressions):
    old = old.replace(expression, f'({channel} * 512 + 127) / 255')
(build / 'camera_quantization_baseline.cpp').write_text(prefix + old, encoding='utf-8')
(build / 'camera_quantization_optimized.cpp').write_text(prefix + body, encoding='utf-8')
