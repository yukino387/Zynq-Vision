import hashlib
import ipaddress
import json
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from receiver import Receiver
from postprocess import CLASS_LABELS, detect


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #20242b; }
QMainWindow, QWidget#root { background: #f3f4f7; }
QFrame#sidebar { background: #ebedf2; border-right: 1px solid #dce0e8; }
QFrame#card { background: white; border: 1px solid #e2e5eb; border-radius: 10px; }
QLabel#muted { color: #687284; }
QLabel#title { font-size: 27px; font-weight: 600; }
QLabel#section { font-size: 16px; font-weight: 600; }
QLabel#number { font-size: 27px; font-weight: 600; }
QLabel#brand { color: #0067c0; font-size: 20px; font-weight: 600; }
QLabel#selected { background: #dce7f3; color: #005aa5; border-left: 3px solid #0067c0; border-radius: 5px; padding: 12px; }
QLabel#badge { background: #eef3fb; color: #32659a; border-radius: 5px; padding: 5px 9px; }
QLabel#preview { background: #f6f7f9; color: #7c8797; border: 1px solid #e6e9ef; border-radius: 8px; }
QLineEdit, QSpinBox { background: white; border: 1px solid #cbd1dc; border-bottom: 1px solid #8993a3; border-radius: 5px; padding: 7px; }
QLineEdit:focus, QSpinBox:focus { border-bottom: 2px solid #0067c0; }
QPushButton { background: white; border: 1px solid #ccd2dc; border-radius: 5px; padding: 9px 14px; }
QPushButton:hover { background: #f0f5fb; border-color: #9abce0; }
QPushButton:pressed { background: #e0ecf9; }
QPushButton#primary { background: #0067c0; color: white; border: 1px solid #0067c0; }
QPushButton#primary:hover { background: #005ba9; }
QPushButton:disabled { background: #f4f5f7; color: #a0a7b3; border-color: #e0e3e9; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { background: white; border: 1px solid #929cac; border-radius: 4px; }
QCheckBox::indicator:checked { background: #0067c0; border: 1px solid #0067c0; border-radius: 4px; }
QDoubleSpinBox { background: white; border: 1px solid #cbd1dc; border-radius: 5px; padding: 6px; }
QTableWidget { background: white; border: none; selection-background-color: #e5f0fc; selection-color: #20242b; }
QHeaderView::section { background: #f5f7fa; color: #687284; border: none; padding: 6px; }
"""


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


def rgb_image(raw):
    pixels = np.frombuffer(raw, dtype="<u2").reshape(416, 416)
    red, green, blue = pixels >> 11, (pixels >> 5) & 63, pixels & 31
    rgb = np.stack(((red << 3) | (red >> 2), (green << 2) | (green >> 4),
                    (blue << 3) | (blue >> 2)), axis=-1).astype(np.uint8)
    return QImage(rgb.data, 416, 416, 416 * 3, QImage.Format.Format_RGB888).copy()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNN Studio · FPGA 视觉上位机")
        self.resize(1180, 900)
        self.setMinimumSize(1040, 820)
        self.worker = None
        self.latest = None
        self.image = None
        self.detections = []
        self.rotation = 0
        self.times = deque(maxlen=30)
        self.count = self.missing = self.byte_count = 0
        self.started = self.last_frame = 0
        self.last_folder = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(248)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 28, 22, 24)
        side.setSpacing(14)
        side.addWidget(label("▦  CNN Studio", "brand"))
        side.addWidget(label("Zynq-7020 视觉工作台", "muted"))
        side.addSpacing(14)
        side.addWidget(label("▣   实时推理", "selected"))
        side.addSpacing(14)
        side.addWidget(label("设备连接", "section"))
        self.board_ip = QLineEdit("169.254.140.110")
        self.local_ip = QLineEdit("169.254.140.109")
        self.board_port = QSpinBox()
        self.local_port = QSpinBox()
        for port, value in ((self.board_port, 5001), (self.local_port, 5002)):
            port.setRange(1, 65535)
            port.setValue(value)
        for title, widget in (("板卡 IP", self.board_ip), ("板卡 UDP 端口", self.board_port),
                              ("电脑以太网 IP", self.local_ip), ("本地 UDP 端口", self.local_port)):
            side.addWidget(label(title, "muted"))
            side.addWidget(widget)
        self.fields = (self.board_ip, self.local_ip, self.board_port, self.local_port)
        self.preview_switch = QCheckBox("接收摄像头预览")
        self.preview_switch.setChecked(True)
        self.preview_switch.toggled.connect(self.change_preview)
        side.addSpacing(8)
        side.addWidget(self.preview_switch)
        self.connect_button = QPushButton("开始连接")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self.toggle_connection)
        side.addWidget(self.connect_button)
        side.addStretch()
        side.addWidget(label("OV5640  ·  RGB565\nYOLOv4-tiny  ·  VOC 20 类", "muted"))
        outer.addWidget(sidebar)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(26, 26, 26, 20)
        body.setSpacing(18)
        heading = QHBoxLayout()
        heading.addWidget(label("实时推理", "title"))
        heading.addStretch()
        self.status = label("●  未连接")
        heading.addWidget(self.status)
        body.addLayout(heading)
        body.addWidget(label("实时目标检测 · FPGA 推理，电脑端解码与 NMS", "muted"))
        settings = QHBoxLayout()
        self.confidence = QDoubleSpinBox()
        self.iou = QDoubleSpinBox()
        for widget, value in ((self.confidence, 0.5), (self.iou, 0.3)):
            widget.setRange(0.01, 1)
            widget.setSingleStep(0.05)
            widget.setValue(value)
            widget.setFixedWidth(90)
            widget.valueChanged.connect(self.update_detection)
        settings.addWidget(label("置信度", "muted"))
        settings.addWidget(self.confidence)
        settings.addSpacing(20)
        settings.addWidget(label("NMS IoU", "muted"))
        settings.addWidget(self.iou)
        settings.addStretch()
        self.detection_count = label("检测目标  0", "badge")
        settings.addWidget(self.detection_count)
        body.addLayout(settings)
        metrics = QHBoxLayout()
        self.metrics = {}
        for key, title, initial in (("fps", "接收帧率", "—"), ("frames", "完整帧", "0"),
                                    ("rate", "接收速率", "—"), ("missing", "跳过帧", "0")):
            frame, layout = card()
            layout.addWidget(label(title, "muted"))
            value = label(initial, "number")
            self.metrics[key] = value
            layout.addWidget(value)
            metrics.addWidget(frame)
        body.addLayout(metrics)

        center = QHBoxLayout()
        center.setSpacing(18)
        preview_card, preview_layout = card()
        top = QHBoxLayout()
        top.addWidget(label("摄像头画面", "section"))
        top.addStretch()
        top.addWidget(label("416 × 416", "badge"))
        preview_layout.addLayout(top)
        self.preview_label = label("等待摄像头画面\n\n连接板卡后，画面将在这里显示。", "preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(380, 380)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview_label, 1)
        preview_footer = QHBoxLayout()
        self.frame_label = label("帧号 —", "muted")
        preview_footer.addWidget(self.frame_label)
        preview_footer.addStretch()
        rotate = QPushButton("旋转 90°")
        rotate.clicked.connect(self.rotate_image)
        preview_footer.addWidget(rotate)
        preview_layout.addLayout(preview_footer)
        center.addWidget(preview_card, 1)

        outputs = QVBoxLayout()
        outputs.setSpacing(18)
        self.output_values = []
        for title, shape, size in (("检测输出 P5", "75 × 13 × 13", "25,350 字节"),
                                   ("检测输出 P4", "75 × 26 × 26", "101,400 字节")):
            frame, layout = card()
            frame.setFixedWidth(252)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(6)
            layout.addWidget(label(title, "section"))
            shape_label = label(shape, "number")
            shape_label.setStyleSheet("font-size: 21px;")
            layout.addWidget(shape_label)
            layout.addWidget(label(f"CHW · int16  /  {size}", "muted"))
            grid = QGridLayout()
            values = []
            for row, text in enumerate(("最小值", "最大值", "均值")):
                grid.addWidget(label(text, "muted"), row, 0)
                value = label("—")
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                grid.addWidget(value, row, 1)
                values.append(value)
            layout.addLayout(grid)
            self.output_values.append(values)
            outputs.addWidget(frame)
        results_card, results_layout = card()
        results_card.setFixedWidth(252)
        results_layout.setContentsMargins(16, 12, 16, 12)
        results_layout.addWidget(label("检测结果", "section"))
        self.results = QTableWidget(0, 2)
        self.results.setHorizontalHeaderLabels(("类别", "置信度"))
        self.results.verticalHeader().hide()
        self.results.setShowGrid(False)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setColumnWidth(0, 116)
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.setMinimumHeight(120)
        results_layout.addWidget(self.results)
        outputs.addWidget(results_card, 1)
        center.addLayout(outputs)
        body.addLayout(center, 1)

        actions = QHBoxLayout()
        self.message = label("准备就绪。连接板卡以开始接收。", "muted")
        self.message.setWordWrap(True)
        actions.addWidget(self.message, 1)
        self.open_button = QPushButton("打开保存目录")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(lambda: os.startfile(self.last_folder))
        self.save_button = QPushButton("保存当前帧")
        self.save_button.setObjectName("primary")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_frame)
        actions.addWidget(self.open_button)
        actions.addWidget(self.save_button)
        body.addLayout(actions)
        outer.addWidget(content, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_status)
        self.timer.start(500)

    def set_status(self, text, color):
        self.status.setText("●  " + text)
        self.status.setStyleSheet(f"color: {color}; font-weight: 600;")

    def toggle_connection(self):
        if self.worker is not None:
            self.connect_button.setEnabled(False)
            self.worker.requestInterruption()
            return
        try:
            for field in (self.local_ip, self.board_ip):
                ipaddress.IPv4Address(field.text().strip())
        except ipaddress.AddressValueError:
            QMessageBox.warning(self, "地址无效", "请输入有效的 IPv4 地址。")
            return
        self.latest = self.image = None
        self.detections = []
        self.results.setRowCount(0)
        self.detection_count.setText("检测目标  0")
        self.times.clear()
        self.count = self.missing = self.byte_count = 0
        self.last_frame = 0
        self.started = time.monotonic()
        self.save_button.setEnabled(False)
        self.preview_label.clear()
        self.preview_label.setText("等待摄像头画面")
        self.frame_label.setText("帧号 —")
        for values in self.output_values:
            for value in values:
                value.setText("—")
        for key, value in self.metrics.items():
            value.setText("0" if key in ("frames", "missing") else "—")
        for field in self.fields:
            field.setEnabled(False)
        worker = Receiver(self.local_ip.text().strip(), self.local_port.value(),
                          self.board_ip.text().strip(), self.board_port.value(),
                          self.preview_switch.isChecked())
        self.worker = worker
        worker.listening.connect(self.on_listening)
        worker.frame.connect(self.on_frame)
        worker.error.connect(self.on_error)
        worker.finished.connect(self.on_stopped)
        self.connect_button.setText("断开连接")
        self.set_status("正在连接", "#9a6700")
        worker.start()

    def on_listening(self):
        self.message.setText("等待板卡发送数据；首次启动需要先完成程序和权重下载。")
        self.set_status("等待板卡", "#9a6700")

    def on_error(self, message):
        self.message.setText(message)
        self.set_status("连接失败", "#b42318")

    def on_stopped(self):
        self.worker.deleteLater()
        self.worker = None
        for field in self.fields:
            field.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("开始连接")
        if self.status.text() != "●  连接失败":
            self.set_status("已断开", "#687284")
            self.message.setText("接收已停止，当前帧可继续保存。")

    def change_preview(self, enabled):
        if self.worker is not None:
            self.worker.preview = enabled
        self.image = None
        self.preview_label.clear()
        self.preview_label.setText("等待摄像头画面" if enabled else "画面预览已关闭\n\n继续接收两路预测张量。")

    def on_frame(self, frame):
        self.latest = frame
        self.last_frame = frame["time"]
        self.times.append(self.last_frame)
        self.count += 1
        self.missing += frame["missing"]
        self.byte_count += sum(map(len, frame["data"].values()))
        self.metrics["frames"].setText(f"{self.count:,}")
        self.metrics["missing"].setText(f"{self.missing:,}")
        if len(self.times) > 1:
            fps = (len(self.times) - 1) / (self.times[-1] - self.times[0])
            self.metrics["fps"].setText(f"{fps:.2f} fps")
        elapsed = self.last_frame - self.started
        self.metrics["rate"].setText(f"{self.byte_count / max(elapsed, .001) / 1024:.0f} KB/s")
        for kind in (0, 1):
            values = np.frombuffer(frame["data"][kind], dtype="<i2")
            minimum, maximum, mean = self.output_values[kind]
            minimum.setText(f"{values.min():,}")
            maximum.setText(f"{values.max():,}")
            mean.setText(f"{values.mean():.1f}")
        if 2 in frame["data"] and self.preview_switch.isChecked():
            self.image = rgb_image(frame["data"][2])
        self.update_detection()
        self.frame_label.setText(f"帧号 {frame['id']:,}")
        self.save_button.setEnabled(True)
        self.set_status("正在接收", "#107c41")
        self.message.setText("实时检测已更新" if self.detections else "当前帧未检测到超过置信度阈值的目标")

    def update_detection(self):
        if self.latest is None:
            return
        begin = time.perf_counter()
        self.detections = detect(self.latest["data"][0], self.latest["data"][1],
                                 self.confidence.value(), self.iou.value())
        self.latest["detections"] = self.detections
        self.latest["thresholds"] = {"confidence": self.confidence.value(), "nms_iou": self.iou.value()}
        self.latest["postprocess_ms"] = (time.perf_counter() - begin) * 1000
        self.detection_count.setText(f"检测目标  {len(self.detections)}")
        self.results.setRowCount(len(self.detections))
        for row, detection in enumerate(self.detections):
            self.results.setItem(row, 0, QTableWidgetItem(CLASS_LABELS[detection["class_id"]]))
            self.results.setItem(row, 1, QTableWidgetItem(f"{detection['score']:.1%}"))
        self.draw_image()

    def check_status(self):
        if self.worker is not None and self.last_frame and time.monotonic() - self.last_frame > 3:
            self.set_status("等待新帧", "#9a6700")
            self.metrics["fps"].setText("0.00 fps")
            self.message.setText("暂未收到新帧，请检查板卡运行状态和网线连接。")

    def draw_image(self):
        if self.image is None:
            return
        display = self.image.transformed(QTransform().rotate(self.rotation))
        transform = QTransform()
        if self.rotation == 90:
            transform.translate(416, 0).rotate(90)
        elif self.rotation == 180:
            transform.translate(416, 416).rotate(180)
        elif self.rotation == 270:
            transform.translate(0, 416).rotate(270)
        painter = QPainter(display)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        for detection in self.detections:
            x1, y1, x2, y2 = detection["box"]
            box = transform.mapRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            painter.setPen(QPen(QColor("#0078d4"), 2))
            painter.drawRect(box)
            text = f"{CLASS_LABELS[detection['class_id']]} {detection['score']:.0%}"
            width = painter.fontMetrics().horizontalAdvance(text) + 12
            tag = QRectF(min(box.left(), 416 - width), max(0, box.top() - 22), width, 22)
            painter.fillRect(tag, QColor("#0067c0"))
            painter.setPen(QColor("white"))
            painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        pixmap = QPixmap.fromImage(display)
        self.preview_label.setPixmap(pixmap.scaled(self.preview_label.size() - QSize(16, 16),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def rotate_image(self):
        self.rotation = (self.rotation + 90) % 360
        self.draw_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "preview_label"):
            self.draw_image()

    def save_frame(self):
        frame = self.latest
        if frame is None:
            return
        destination = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if destination:
            try:
                folder = self.write_frame(frame, Path(destination))
                self.last_folder = str(folder)
                self.open_button.setEnabled(True)
                self.message.setText(f"已保存帧 {frame['id']} 至 {folder.name}")
            except OSError as exc:
                QMessageBox.warning(self, "保存失败", str(exc))

    def write_frame(self, frame, destination):
        folder = destination / f"frame_{frame['id']:06d}_{datetime.now():%Y%m%d_%H%M%S_%f}"
        folder.mkdir(parents=True)
        report = {"frame": frame["id"], "streams": {}}
        detection_report = {"frame": frame["id"], "image_size": [416, 416],
            "thresholds": frame.get("thresholds"), "postprocess_ms": frame.get("postprocess_ms"),
            "detections": frame.get("detections", [])}
        for kind, raw in frame["data"].items():
            name = ("out0.bin", "out1.bin", "preview_rgb565.bin")[kind]
            (folder / name).write_bytes(raw)
            values = np.frombuffer(raw, dtype="<u2" if kind == 2 else "<i2")
            report["streams"][name] = {"bytes": len(raw), "min": int(values.min()),
                "max": int(values.max()), "sha256": hashlib.sha256(raw).hexdigest()}
            if kind == 2 and not rgb_image(raw).save(str(folder / "preview.png")):
                raise OSError("无法保存预览图片")
        (folder / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (folder / "detections.json").write_text(json.dumps(detection_report, indent=2), encoding="utf-8")
        return folder

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.requestInterruption()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    sys.exit(app.exec())
