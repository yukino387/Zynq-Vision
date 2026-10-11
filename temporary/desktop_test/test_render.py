import sys
import time
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "camera/desktop"))
from PySide6.QtWidgets import QApplication
from app import STYLE, Window

here = Path(__file__).resolve().parent
application = QApplication([])
application.setStyleSheet(STYLE)
window = Window()
window.show()
application.processEvents()
saved = sorted((here / "build/saved").glob("frame_*"))[-1]
out0 = np.full((3, 25, 13, 13), -16384, dtype="<i2")
out1 = np.full((3, 25, 26, 26), -16384, dtype="<i2")
out0[0, :4, 6, 6] = 0
out0[0, 4, 6, 6] = 4096
out0[0, 19, 6, 6] = 4096
frame = {"id": 1, "time": time.monotonic(), "missing": 0,
         "data": {0: out0.tobytes(), 1: out1.tobytes(), 2: (saved / "preview_rgb565.bin").read_bytes()}}
window.started = time.monotonic() - 1
window.on_frame(frame)
assert window.results.rowCount() == 1
assert window.results.item(0, 0).text() == "人"
assert window.detections[0]["class_name"] == "person"
window.grab().save(str(here / "build/synthetic_boxes.png"))
for angle in (90, 180, 270, 0):
    window.rotate_image()
    assert window.rotation == angle
    assert not window.preview_label.pixmap().isNull()
window.close()
print("PASS: detection label, overlay and four rotations (synthetic prediction)")
