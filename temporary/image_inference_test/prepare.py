import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve()
for artifact in ('out0.bin', 'out1.bin', 'inference_report.json'):
    (HERE / artifact).unlink(missing_ok=True)
layers = [("BasicConv1", 864, 32, "w", "b"),
          ("BasicConv2", 18432, 64, "w", "b"),
          ("BasicConv3", 2359296, 512, "w", "b")]
for index, channels in enumerate((64, 128, 256), 1):
    for conv, count, bias in ((1, channels * channels * 9, channels),
                              (2, (channels // 2) ** 2 * 9, channels // 2),
                              (3, (channels // 2) ** 2 * 9, channels // 2),
                              (4, channels * channels, channels)):
        layers.append((f"ResBlock{index}", count, bias, f"w{conv}", f"b{conv}"))
layers += [("conv_forP5", 131072, 256, "w", "b"),
           ("yolo_headP4", 884736, 256, "w1", "b1"),
           ("yolo_headP4", 19200, 75, "w2", "b2"),
           ("yolo_headP5", 1179648, 512, "w1", "b1"),
           ("yolo_headP5", 38400, 75, "w2", "b2"),
           ("upsample", 32768, 128, "w", "b")]
staging = HERE / "pc_files"
staging.mkdir(exist_ok=True)
report, offset = [], 0
with (staging / "all_weights.bin").open("wb") as payload:
    for folder, weight_count, bias_count, wname, bname in layers:
        for name, count in ((wname, weight_count), (bname, bias_count)):
            relative = f"{folder}/{name}.bin"
            raw = (ROOT / relative).read_bytes()
            if len(raw) != count * 4:
                raise ValueError(f"{relative}: expected {count * 4} bytes, got {len(raw)}")
            values = array.array("f")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            quantized = []
            digest = 2166136261
            for value in values:
                if not math.isfinite(value):
                    raise ValueError(f"{relative}: non-finite parameter")
                scaled = value * 512
                result = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
                if not -32768 <= result <= 32767:
                    raise ValueError(f"{relative}: quantization overflow ({value})")
                quantized.append(result)
                for byte in struct.pack("<h", result):
                    digest = ((digest ^ byte) * 16777619) & 0xffffffff
            report.append(dict(file=relative, count=count, bytes=len(raw),
                               float_min=min(values), float_max=max(values),
                               int16_min=min(quantized), int16_max=max(quantized),
                               fnv1a=digest, sha256=hashlib.sha256(raw).hexdigest(), offset=offset))
            payload.write(raw)
            offset += count
header = ['#ifndef FULL_WEIGHT_EXPECTED_H', '#define FULL_WEIGHT_EXPECTED_H',
          '#include <cstddef>', '#include <cstdint>',
          'struct ExpectedFile { const char* name; std::size_t count, offset; int low, high; uint32_t hash; };',
          f'enum {{ FILE_COUNT = {len(report)}, TOTAL_FLOATS = {offset} }};',
          'static const ExpectedFile expected_files[FILE_COUNT] = {']
for item in report:
    header.append('    {"%s", %d, %d, %d, %d, %du},' %
                  (item['file'], item['count'], item['offset'], item['int16_min'],
                   item['int16_max'], item['fnv1a']))
header += ['};', '#endif', '']
(HERE / 'expected.h').write_text('\n'.join(header), encoding='ascii')
directory = str(ROOT).replace('\\', '/').encode('utf-8') + b'\0'
if len(directory) > 1024:
    raise ValueError('Directory exceeds target staging buffer')
(staging / 'directory.bin').write_bytes(directory)
(HERE / 'weight_report.json').write_text(json.dumps(
    dict(directory=str(ROOT), layers=len(layers), files=len(report), total_parameters=offset,
         quantization='round(float32 * 512) -> int16_t', parameters=report),
    ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['Layer/file | Count | Float min/max | Int16 min/max']
for item in report:
    lines.append(f"{item['file']} | {item['count']} | {item['float_min']:.9g} / {item['float_max']:.9g} | {item['int16_min']} / {item['int16_max']}")
(HERE / 'per_layer_stats.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'PC files PASS: {len(layers)} layers, {len(report)} files, {offset} parameters')

# HLS_pj/yolo.py: direct bicubic RGB resize, float32 /255, then CHW.
import numpy as np
from PIL import Image
import zipfile
if len(sys.argv) > 2:
    image_path = Path(sys.argv[2]).resolve()
else:
    author = ROOT.parent.parent
    archive = next(author.glob("*/yolov4-tiny-pytorch-master.zip"))
    with zipfile.ZipFile(archive) as zipped:
        entry = "yolov4-tiny-pytorch-master/img/street.jpg"
        image_path = HERE / "street.jpg"
        image_path.write_bytes(zipped.read(entry))
with Image.open(image_path) as source_image:
    original_size = source_image.size
    resized = source_image.convert("RGB").resize((416, 416), Image.Resampling.BICUBIC)
    resized.save(HERE / "resized_input.png")
    pixels = np.array(resized, dtype=np.float32) / np.float32(255.0)
chw = np.ascontiguousarray(pixels.transpose(2, 0, 1))
scaled = chw * np.float32(512.0)
quantized = np.floor(scaled + np.float32(0.5)).astype("<i2")
quantized.tofile(staging / "input.bin")
hash_value = 2166136261
for byte in quantized.tobytes():
    hash_value = ((hash_value ^ byte) * 16777619) & 0xffffffff
(HERE / "input_expected.h").write_text(
    f"static const unsigned INPUT_HASH = {hash_value}u;\n"
    f"static const int INPUT_MIN = {quantized.min()}, INPUT_MAX = {quantized.max()};\n",
    encoding="ascii")
(HERE / "input_report.json").write_text(json.dumps(dict(
    image=str(image_path), original_size=original_size, input_shape=[3,416,416],
    preprocessing="RGB; direct bicubic resize; float32 /255; CHW; round-away-from-zero *512",
    float_min=float(chw.min()), float_max=float(chw.max()),
    int16_min=int(quantized.min()), int16_max=int(quantized.max()),
    fnv1a=hash_value, count=int(quantized.size)), indent=2), encoding="utf-8")
print(f"Image prepared: RGB CHW 3x416x416; float [{chw.min()}, {chw.max()}]; int16 [{quantized.min()}, {quantized.max()}]")
