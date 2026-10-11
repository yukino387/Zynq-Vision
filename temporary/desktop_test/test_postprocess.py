import math
import sys
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "camera/desktop"))
from postprocess import detect, nms


class PostprocessTest(unittest.TestCase):
    def test_chw_scale_anchor_and_confidence(self):
        out0 = np.full((3, 25, 13, 13), -16384, dtype="<i2")
        out1 = np.full((3, 25, 26, 26), -16384, dtype="<i2")
        out0[0, :4, 6, 6] = 0
        out0[0, 4, 6, 6] = 1536
        out0[0, 19, 6, 6] = 1536
        detections = detect(out0.tobytes(), out1.tobytes())
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["class_name"], "person")
        self.assertAlmostEqual(detections[0]["score"], (1 / (1 + math.exp(-3))) ** 2)
        np.testing.assert_allclose(detections[0]["box"],
            [208 - 2.5312 * 16, 167, 208 + 2.5312 * 16, 249])
        self.assertEqual(detect(out0.tobytes(), out1.tobytes(), confidence=.95), [])

    def test_p4_anchors(self):
        out0 = np.full((3, 25, 13, 13), -16384, dtype="<i2")
        out1 = np.full((3, 25, 26, 26), -16384, dtype="<i2")
        out1[0, :4, 12, 12] = 0
        out1[0, 4, 12, 12] = 4096
        out1[0, 24, 12, 12] = 4096
        result = detect(out0.tobytes(), out1.tobytes())[0]
        self.assertEqual(result["class_name"], "tvmonitor")
        np.testing.assert_allclose(result["box"], [188.5, 186.5, 211.5, 213.5])

    def test_nms_keeps_different_classes(self):
        boxes = np.array([[0, 0, 100, 100], [1, 1, 101, 101], [0, 0, 100, 100], [200, 200, 300, 300]])
        scores = np.array([.9, .8, .7, .6])
        classes = np.array([14, 14, 19, 14])
        self.assertEqual(nms(boxes, scores, classes, .3), [0, 2, 3])


if __name__ == "__main__":
    unittest.main()
