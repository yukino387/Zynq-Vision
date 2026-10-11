import socket
import struct
import time

from PySide6.QtCore import QThread, Signal


SIZES = {0: 75 * 13 * 13 * 2, 1: 75 * 26 * 26 * 2, 2: 416 * 416 * 2}


class FrameAssembler:
    def __init__(self):
        self.frames = {}
        self.last = None

    def feed(self, packet, preview):
        if len(packet) <= 20:
            return None
        magic, frame, kind, total, offset = struct.unpack_from("<5I", packet)
        payload = packet[20:]
        required = (0, 1, 2) if preview else (0, 1)
        if (magic != 0x314F4C59 or kind not in required or total != SIZES[kind]
                or offset >= total or offset % 1400
                or len(payload) != min(1400, total - offset)):
            return None
        if self.last is not None and frame <= self.last:
            return None
        if frame not in self.frames:
            self.frames[frame] = {}
            while len(self.frames) > 3:
                del self.frames[min(self.frames)]
            if frame not in self.frames:
                return None
        streams = self.frames[frame]
        data, offsets = streams.setdefault(kind, (bytearray(total), set()))
        data[offset:offset + len(payload)] = payload
        offsets.add(offset)
        if not all(k in streams and len(streams[k][1]) == (SIZES[k] + 1399) // 1400
                   for k in required):
            return None
        result = {"id": frame, "data": {k: bytes(streams[k][0]) for k in required},
                  "missing": 0 if self.last is None else frame - self.last - 1,
                  "time": time.monotonic()}
        self.last = frame
        self.frames = {key: value for key, value in self.frames.items() if key > frame}
        return result


class Receiver(QThread):
    frame = Signal(object)
    listening = Signal()
    error = Signal(str)

    def __init__(self, local_ip, local_port, board_ip, board_port, preview):
        super().__init__()
        self.local = (local_ip, local_port)
        self.board = (board_ip, board_port)
        self.preview = preview

    def run(self):
        assembler = FrameAssembler()
        registered = 0
        preview = self.preview
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                sock.bind(self.local)
                sock.settimeout(0.2)
                self.listening.emit()
                while not self.isInterruptionRequested():
                    now = time.monotonic()
                    if preview != self.preview:
                        preview = self.preview
                        assembler.frames.clear()
                        registered = 0
                    if now - registered >= 1:
                        sock.sendto(bytes([int(preview)]), self.board)
                        registered = now
                    try:
                        packet, address = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    if address != self.board:
                        continue
                    complete = assembler.feed(packet, preview)
                    if complete is not None:
                        self.frame.emit(complete)
        except OSError as exc:
            self.error.emit(f"网络错误：{exc}")
