import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "camera/desktop"))
from receiver import FrameAssembler, SIZES


def packets(frame, kind):
    raw = bytes((i * 7 + kind) % 256 for i in range(SIZES[kind]))
    return raw, [struct.pack("<5I", 0x314f4c59, frame, kind, len(raw), offset)
                 + raw[offset:offset + 1400] for offset in range(0, len(raw), 1400)]


class ProtocolTest(unittest.TestCase):
    def test_reordered_duplicate_and_invalid_packets(self):
        assembler = FrameAssembler()
        expected = {}
        result = None
        self.assertIsNone(assembler.feed(b"invalid", True))
        for kind in (2, 1, 0):
            raw, chunks = packets(10, kind)
            expected[kind] = raw
            self.assertIsNone(assembler.feed(chunks[-1], True))
            self.assertIsNone(assembler.feed(chunks[-1], True))
            for chunk in reversed(chunks[:-1]):
                result = assembler.feed(chunk, True)
        self.assertEqual(result["data"], expected)
        self.assertEqual(result["id"], 10)
        self.assertIsNone(assembler.feed(chunks[0], True))

    def test_loss_and_preview_off(self):
        assembler = FrameAssembler()
        result = None
        for frame in (3, 5):
            for kind in (0, 1):
                raw, chunks = packets(frame, kind)
                for chunk in chunks:
                    result = assembler.feed(chunk, False)
        self.assertEqual(result["missing"], 1)
        self.assertEqual(set(result["data"]), {0, 1})
        for frame in (6, 7, 8, 9, 6):
            assembler.feed(packets(frame, 0)[1][0], False)
        self.assertLessEqual(len(assembler.frames), 3)
        bad = struct.pack("<5I", 0x314f4c59, 10, 0, SIZES[0], SIZES[0]) + b"x"
        self.assertIsNone(assembler.feed(bad, False))


if __name__ == "__main__":
    unittest.main()
