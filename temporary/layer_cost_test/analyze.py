"""Analytical convolution cost model; no FPGA execution or latency simulation."""
import csv
import html
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "build"
FREQUENCY_HZ = 100_000_000


def constructors(filename, classname):
    source = (ROOT / filename).read_text(encoding="utf-8")
    return [(name, tuple(map(int, args.split(",")))) for name, args in
            re.findall(r"(\w+)\s*=\s*new " + classname + r"\(([^()]+)\)", source)
            if re.fullmatch(r"[\d,\s]+", args)]


def estimate(name, h, w, k, stride, pad, cin, cout):
    oh = (h + 2 * pad - k) // stride + 1
    ow = (w + 2 * pad - k) // stride + 1
    mac = oh * ow * cin * cout * k * k
    # Author HLS: 3x3 tiles 13x13, Tn=4, Tm=32;
    # 1x1 tiles 169 pixels, Tn=4, Tm=8. II=1 compute loops.
    tiles = math.ceil(oh / 13) * math.ceil(ow / 13) if k == 3 else math.ceil(oh * ow / 169)
    tm = 32 if k == 3 else 8
    cycles = tiles * math.ceil(cin / 4) * math.ceil(cout / tm) * 169 * k * k
    input_bytes = h * w * cin * 2
    output_bytes = oh * ow * cout * 2
    weight_bytes = (cin * cout * k * k + cout) * 2
    return dict(layer=name, input=f"{cin}x{h}x{w}", output=f"{cout}x{oh}x{ow}",
                kernel=k, mac=mac, ideal_compute_ms=cycles / FREQUENCY_HZ * 1000,
                input_bytes=input_bytes, output_bytes=output_bytes,
                weight_bytes=weight_bytes,
                unique_data_bytes=input_bytes + output_bytes + weight_bytes)


def main():
    basic = dict(constructors("cspdarknet.cpp", "BasicConv"))
    layers = [estimate("backbone." + n, *basic[n]) for n in ("basic_conv1", "basic_conv2")]
    for name, (h, w, cin, cout) in constructors("cspdarknet.cpp", "Resblock_body"):
        configs = [(h, w, 3, 1, 1, cin, cout),
                   (h, w, 3, 1, 1, cout // 2, cout // 2),
                   (h, w, 3, 1, 1, cout // 2, cout // 2),
                   (h, w, 1, 1, 0, cout, cout)]
        layers.extend(estimate(f"{name}.conv{i}", *args) for i, args in enumerate(configs, 1))
    layers.append(estimate("backbone.basic_conv3", *basic["basic_conv3"]))
    head = dict(constructors("yolo4_tiny.cpp", "BasicConv"))
    layers.extend(estimate(n, *head[n]) for n in ("conv_forP5_conv", "yolo_headP5_basic_conv1"))
    # These two direct conv_leakyrelu calls are explicit in Yolo4_Tiny::forward.
    layers.append(estimate("headP5.predict", 13, 13, 1, 1, 0, 512, 75))
    layers.extend(estimate(n, *head[n]) for n in ("upsample_conv", "yolo_headP4_basic_conv1"))
    layers.append(estimate("headP4.predict", 26, 26, 1, 1, 0, 256, 75))
    total_mac = sum(x["mac"] for x in layers)
    total_ms = sum(x["ideal_compute_ms"] for x in layers)
    assert len(layers) == 21 and total_mac == 3_407_213_056
    assert abs(total_ms - 309.77024) < 1e-6
    for row in layers:
        row["compute_share_percent"] = row["ideal_compute_ms"] / total_ms * 100
    measured = None
    measurements = ROOT / "temporary/winui_test/board_results.json"
    if measurements.exists():
        stats = json.loads(measurements.read_text(encoding="utf-8"))["stats"]
        times = [s[7] / 1000 for s in stats
                 if len(s) == 12 and s[1] == 0 and (s[3] & 1) and not (s[3] & 2) and s[7] > 0]
        if times:
            measured = statistics.median(times)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "layers.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(layers[0]))
        writer.writeheader()
        writer.writerows(layers)
    ranked = sorted(layers, key=lambda x: x["ideal_compute_ms"], reverse=True)
    rows = "".join(f'<tr><td>{html.escape(x["layer"])}</td><td>{x["input"]} → {x["output"]}</td>'
                   f'<td>{x["mac"] / 1e6:.2f}</td><td>{x["ideal_compute_ms"]:.3f}</td>'
                   f'<td><div style="width:{x["ideal_compute_ms"] / ranked[0]["ideal_compute_ms"] * 240:.1f}px" '
                   f'class="bar"></div></td><td>{x["unique_data_bytes"] / 1e6:.3f}</td></tr>' for x in ranked)
    measured_text = f"已有整网实测中位数：{measured:.3f} ms。" if measured else "未找到整网实测数据。"
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>各层计算成本估算</title>
<style>body{{font:15px 'Segoe UI',sans-serif;background:#f5f7fa;color:#182233;margin:36px}}main{{max-width:1150px;margin:auto}}
table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #eee}}
.bar{{height:14px;background:#167bc1;border-radius:3px}}p{{line-height:1.7}}h1{{font-size:26px}}</style><main>
<h1>YOLOv4-tiny 各层计算成本估算</h1><p>21 层卷积 · INT16 · 100 MHz · {total_mac / 1e9:.3f} GMAC</p>
<p>理想卷积计算合计：<b>{total_ms:.3f} ms</b>。{measured_text}<br>
这是按当前 HLS 分块和计算循环推算的成本，不是逐层上板耗时，也不是 RTL 周期仿真。
未计入加载、写回、流水线启动、池化、放大、缓存维护和 PS 调度；已有重叠部分不能直接相加。</p>
<table><tr><th>层</th><th>输入 → 输出（通道×高×宽）</th><th>百万次乘加</th><th>理想计算 ms</th><th>相对计算成本</th><th>唯一数据 MB</th></tr>{rows}</table>
<p>唯一数据量按输入、权重含 bias、输出各出现一次计算；实际分块会重复读取，因此这不是实际 DDR 流量。
INT8 只减小数据位宽时，乘加次数不变，不能把上述计算时间直接除以二。</p></main></html>'''
    (OUT / "layers.html").write_text(page, encoding="utf-8")
    print(f"21 convolution layers; MAC={total_mac:,}; ideal compute={total_ms:.5f} ms")
    print(measured_text)
    for row in ranked[:5]:
        print(f'{row["layer"]}: {row["ideal_compute_ms"]:.3f} ms ideal, {row["mac"] / 1e6:.2f} MMAC')
    print(OUT / "layers.html")


if __name__ == "__main__":
    main()
