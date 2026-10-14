"""Render a simplified three-panel architecture poster for the current accelerator.

Data source (verified against HEAD ca6a832):
  hardware/hls/src/top.cpp, std_conv.cpp, type.h
  hardware/camera/base_system.tcl, build.tcl, ov5640_capture.v
  basic_op.cpp, cspdarknet.cpp, yolo4_tiny.cpp, camera/udp_output.cpp
  postroute utilization report + board median timings
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "architecture.png"

W, H = 2000, 1230
BG = "#EEF2F7"
PANEL = "#FFFFFF"
PANEL_EDGE = "#D3DCE6"
INK = "#1B2733"
SUB = "#5B6B7C"
ARROW = "#7A8A9A"

BLUE = ("#E7F0FE", "#2D6CDF")
GREEN = ("#E4F6EA", "#2E9E5B")
GRAY = ("#EDF1F5", "#5B6B7C")
ORANGE = ("#FFF1DE", "#E08A18")

REG = "C:/Windows/Fonts/msyh.ttc"
BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size)


F = {
    "title": font(46, True),
    "meta": font(26, False),
    "panel": font(34, True),
    "box": font(29, True),
    "line": font(24, False),
    "small": font(22, False),
    "tiny": font(20, False),
    "loop": font(30, True),
}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def text_w(s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def center(cx, y, s, f, fill=INK):
    d.text((cx - text_w(s, f) / 2, y), s, font=f, fill=fill)


def panel(x0, y0, x1, y1, heading):
    d.rounded_rectangle([x0, y0, x1, y1], 18, fill=PANEL, outline=PANEL_EDGE, width=2)
    d.text((x0 + 28, y0 + 20), heading, font=F["panel"], fill=INK)


def box(x, y, w, h, title, lines, colors=GRAY, title_f=None, line_f=None):
    fill, edge = colors
    d.rounded_rectangle([x, y, x + w, y + h], 14, fill=fill, outline=edge, width=3)
    tf = title_f or F["box"]
    lf = line_f or F["line"]
    block = (tf.size + 10) + len(lines) * (lf.size + 9)
    top = y + (h - block) / 2
    center(x + w / 2, top, title, tf, edge)
    yy = top + tf.size + 16
    for line in lines:
        center(x + w / 2, yy, line, lf, INK)
        yy += lf.size + 9


def arrow(x0, y0, x1, y1, width=5, color=ARROW, head=17):
    d.line([x0, y0, x1, y1], fill=color, width=width)
    if abs(y1 - y0) < 1:
        s = 1 if x1 > x0 else -1
        d.polygon([(x1, y1), (x1 - s * head, y1 - head * 0.62),
                   (x1 - s * head, y1 + head * 0.62)], fill=color)
    else:
        s = 1 if y1 > y0 else -1
        d.polygon([(x1, y1), (x1 - head * 0.62, y1 - s * head),
                   (x1 + head * 0.62, y1 - s * head)], fill=color)


def chip(cx, cy, label, colors=GRAY, f=None, pad=18):
    f = f or F["small"]
    fill, edge = colors
    w = text_w(label, f) + pad * 2
    h = f.size + 18
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], h / 2,
                        fill=fill, outline=edge, width=2)
    center(cx, cy - f.size / 2 - 3, label, f, edge)
    return w


# ---------------------------------------------------------------- title band
d.rectangle([0, 0, W, 92], fill="#1B2733")
d.text((48, 18), "Zynq-7020 · YOLOv4-tiny 实时推理加速器", font=F["title"], fill="#FFFFFF")
meta = "PL 142.857132 MHz   ·   实测 2.97 FPS   ·   LUT 76%   BRAM 51%   DSP 91%"
d.text((W - 48 - text_w(meta, F["meta"]), 34), meta, font=F["meta"], fill="#9FC0E8")

# ------------------------------------------------------- panel 1 : the journey
panel(24, 108, 1976, 404, "① 一帧的旅程   采集 → 转换 → 推理 → 显示")
BW, BH, GAP = 286, 136, 40
PITCH = BW + GAP
BY = 196
items = [
    ("OV5640 摄像头", ["416×416 RGB565", "25 MHz DVP 接口"], ORANGE),
    ("DDR 图像缓冲", ["pixels[2] 双缓冲", "下一帧采集与推理重叠"], GRAY),
    ("PS 转换为网络输入", ["RGB565 → CHW INT16", "≈ 4.6 ms"], BLUE),
    ("21 层推理", ["conv_0 复用 28 次", "311 ms"], GREEN),
    ("DDR 输出张量", ["out0  75×13×13", "out1  75×26×26"], GRAY),
    ("UDP → WinUI 3 上位机", ["decode · NMS", "显示 / 录制"], ORANGE),
]
for i, (title, lines, colors) in enumerate(items):
    box(48 + i * PITCH, BY, BW, BH, title, lines, colors)
for i, lab in enumerate(["采集", "转换", "逐层推理", "分片发送", "显示"]):
    x0 = 48 + i * PITCH + BW
    arrow(x0 + 6, BY + BH / 2, x0 + GAP - 6, BY + BH / 2)
    center(x0 + GAP / 2, BY - 32, lab, F["tiny"], SUB)

budget = [("采集 12 ms", 12, ORANGE), ("转换 4.6", 4.6, BLUE),
          ("推理 311 ms   占单帧 92%", 311, GREEN), ("发送 9", 9.4, ORANGE)]
bx0, bx1, byy = 48, 1952, 356
scale = (bx1 - bx0) / sum(m for _, m, _ in budget)
cursor = bx0
for lab, ms, colors in budget:
    width = ms * scale
    d.rectangle([cursor, byy, cursor + width, byy + 30], fill=colors[0],
                outline=colors[1], width=2)
    if width > 180:
        center(cursor + width / 2, byy + 3, lab, F["tiny"], colors[1])
    cursor += width
d.text((bx0, byy + 36), "单帧 ≈ 337 ms", font=F["small"], fill=SUB)
tail = "推理是唯一的大头：其余三项合计不到 26 ms"
d.text((bx1 - text_w(tail, F["small"]), byy + 36), tail, font=F["small"], fill=SUB)

# --------------------------------------------- panel 2 : PS <-> PL turn-around
panel(24, 428, 1976, 724, "② 推理内部   PS 逐层派发，PL 一次只算一层")
P2Y, P2H = 556, 128
box(150, P2Y, 400, P2H, "PS 逐层调度", ["写寄存器：地址 / 尺寸 / kernel", "启动后忙等完成"], BLUE)
box(800, P2Y, 400, P2H, "conv_0 加速器", ["3×3 卷积 · 1×1 卷积", "池化 · 上采样"], GREEN)
box(1450, P2Y, 400, P2H, "DDR 特征图 / 权重", ["PL 直接读写", "PS 维护缓存一致性"], GRAY)
arrow(556, P2Y + 40, 794, P2Y + 40, width=5)
arrow(794, P2Y + 88, 556, P2Y + 88, width=5)
center(675, P2Y - 28, "AXI-Lite 配置 + Start / IsDone", F["tiny"], SUB)
arrow(1206, P2Y + 64, 1444, P2Y + 64, width=5)
center(1325, P2Y - 28, "AXI 读写（4×FM + 4×W）", F["tiny"], SUB)
d.line([350, P2Y + P2H + 18, 1650, P2Y + P2H + 18], fill=ARROW, width=2)
for cx in (350, 1650):
    d.line([cx, P2Y + P2H + 4, cx, P2Y + P2H + 32], fill=ARROW, width=2)
    d.line([cx, P2Y + P2H + 4, cx, 506], fill=ARROW, width=2)
d.line([350, 506, 1650, 506], fill=ARROW, width=2)
d.polygon([(1650, 506), (1633, 497), (1633, 515)], fill=ARROW)
center(1000, 468, "× 28 次（21 卷积 + 6 池化 + 1 上采样）", F["loop"], "#B03A2E")
center(1000, 690, "严格串行：启动 → 忙等 IsDone → 维护缓存。没有层间流水，也没有第二个 IP 并行。",
       F["small"], SUB)

# ------------------------------------------------ panel 3 : inside the engine
panel(24, 748, 1976, 1128, "③ 加速器内部   一条数据通路，两级双缓冲")
P3Y, P3H = 856, 156
box(120, P3Y, 460, P3H, "① 读 DDR", ["4 个平面通道并行", "各自独立握手与零填充"], GRAY)
box(690, P3Y, 620, P3H, "② 176 个乘法器同时算",
    ["44 个输出 × 4 个输入通道", "每周期出 1 拍结果"], GREEN)
box(1420, P3Y, 460, P3H, "③ 写 DDR", ["26×26 输出块", "只保护通道边界"], GRAY)
arrow(586, P3Y + P3H / 2, 684, P3Y + P3H / 2, width=6)
arrow(1316, P3Y + P3H / 2, 1414, P3Y + P3H / 2, width=6)
for x0, x1, y, label, colors in (
        (120, 1310, 1044, "双缓冲 1    读下一块  ⟷  算当前块（输入通道 4 个一换）", BLUE),
        (690, 1880, 1096, "双缓冲 2    算下一块  ⟷  写当前块（输出 26×26 块一换）", GREEN)):
    d.line([x0, y, x1, y], fill=colors[1], width=3)
    for cx in (x0, x1):
        d.line([cx, y - 12, cx, y + 12], fill=colors[1], width=3)
    center((x0 + x1) / 2, y + 16, label, F["tiny"], colors[1])
center(1000, 814, "输出块尺寸锁死在 26 或 13 —— 416 输入时每一级特征图都是 13 的倍数，刚好整除。",
       F["small"], SUB)

# ------------------------------------------------------------------- footer
d.rectangle([0, 1148, W, H], fill="#1B2733")
chips = ["28 次硬件启动 / 帧", "推理 311 ms", "帧周期 337 ms", "2.97 FPS",
         "WNS +0.118 ns", "DSP 201 / 220"]
cx = 60
for label in chips:
    w = text_w(label, F["small"]) + 36
    chip(cx + w / 2, 1148 + (H - 1148) / 2, label, ("#243447", "#7FB2E8"))
    cx += w + 22

img.save(OUT)
print(OUT)
