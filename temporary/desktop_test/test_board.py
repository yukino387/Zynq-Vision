import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "camera/desktop"))
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from app import STYLE, Window

here = Path(__file__).resolve().parent
application = QApplication([])
application.setStyle("Fusion")
application.setFont(QFont("Microsoft YaHei UI", 10))
application.setStyleSheet(STYLE)
window = Window()
window.show()
state = {"phase": 0, "count": 0, "errors": [], "saved": ""}
deadline = time.monotonic() + 35


def inspect(frame):
    try:
        state["count"] += 1
        assert len(frame["data"][0]) == 25350
        assert len(frame["data"][1]) == 101400
        if state["phase"] == 0 and state["count"] >= 3:
            assert 2 in frame["data"]
            assert window.image is not None
            folder = window.write_frame(frame, here / "build/saved")
            for kind, name in ((0, "out0.bin"), (1, "out1.bin"), (2, "preview_rgb565.bin")):
                assert (folder / name).read_bytes() == frame["data"][kind]
            state["saved"] = str(folder)
            assert (folder / "detections.json").exists()
            state["detections"] = frame["detections"]
            state["postprocess_ms"] = frame["postprocess_ms"]
            window.grab().save(str(here / "build/window.png"))
            window.rotate_image()
            assert window.rotation == 90
            window.preview_switch.setChecked(False)
            state["phase"] = 1
        elif state["phase"] == 1 and 2 not in frame["data"]:
            window.preview_switch.setChecked(True)
            state["phase"] = 2
        elif state["phase"] == 2 and 2 in frame["data"]:
            assert window.image is not None
            window.toggle_connection()
            state["phase"] = 3
    except Exception as exc:
        state["errors"].append(repr(exc))
        window.close()
        application.quit()


def stopped():
    if state["phase"] == 3:
        window.toggle_connection()
        window.worker.frame.connect(reconnected)


def reconnected(frame):
    state["phase"] = 4
    state["reconnected_id"] = frame["id"]
    window.close()
    application.quit()


def timeout():
    if time.monotonic() > deadline:
        state["errors"].append("Board test timed out: " + window.message.text())
        window.close()
        application.quit()


(here / "build").mkdir(exist_ok=True)
window.toggle_connection()
window.worker.frame.connect(inspect)
window.worker.finished.connect(stopped)
timer = QTimer()
timer.timeout.connect(timeout)
timer.start(500)
application.exec()
state["pass"] = state["phase"] == 4 and not state["errors"]
(here / "build/result.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
print(json.dumps(state), flush=True)
sys.exit(0 if state["pass"] else 1)
