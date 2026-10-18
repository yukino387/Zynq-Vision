import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'camera/training'))
from data import preprocess
from detection import loss, metrics
from pl_model import FixedGraph, COMMANDS, coefficients, pack_weights, unpack_weights, requant, validate_payload

OUT = Path(__file__).parent / 'artifacts'
torch.set_num_threads(4)


def fixtures():
    OUT.mkdir(exist_ok=True)
    items = []
    for i in range(3):
        image = np.random.default_rng(7020 + i).integers(30, 200, (416, 416, 3), dtype=np.uint8)
        image[60:130, 40 + i * 20:150 + i * 20] = [220, 50, 80]
        path = OUT / f'image-{i}.png'
        Image.fromarray(image).save(path)
        items.append({'id': str(i), 'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'width': 416, 'height': 416, 'split': 'train' if i < 2 else 'val', 'boxes': [{'classId': i, 'x1': 40 + i * 20, 'y1': 60, 'x2': 150 + i * 20, 'y2': 130}]})
    for mode in ('GRAY', 'RGB'):
        spec = {'options': {'colorMode': mode, 'epochs': 1, 'batchSize': 2, 'learningRate': .001, 'seed': 7020, 'device': 'cpu'}, 'items': items, 'version': f'TEST-{mode}', 'datasetChecksum': 'test'}
        (OUT / f'{mode}-spec.json').write_text(json.dumps(spec), encoding='utf-8')


class Layout(unittest.TestCase):
    @unittest.skipIf(torch.cuda.is_available(), 'This check uses a CPU-only runtime')
    def test_cuda_request_never_falls_back_to_cpu(self):
        from train import run
        with self.assertRaisesRegex(ValueError, 'CUDA unavailable'):
            run({'options': {'seed': 7020, 'device': 'cuda'}}, OUT / 'no-cpu-fallback')

    def test_detection_loss_handles_anchor_collisions_and_metrics(self):
        outputs = [torch.zeros(1, 33, size, size, requires_grad=True) for size in (7, 14)]
        boxes = [torch.tensor([[0., .1, .1, .3, .3], [1., .1, .1, .3, .3]])]
        value = loss(outputs, boxes)
        self.assertTrue(torch.isfinite(value))
        value.backward()
        self.assertGreater(outputs[0].grad.abs().sum() + outputs[1].grad.abs().sum(), 0)
        result = metrics([[(.9, 0, np.array([.1, .1, .3, .3]))]], [torch.tensor([[0., .1, .1, .3, .3]])])
        self.assertEqual(result['mAP50'], 1.)
        self.assertEqual(result['precision'], 1.)
        self.assertEqual(result['recall'], 1.)

    def test_hls_weight_addresses_independently(self):
        for co, ci, k in [(32, 1, 3), (32, 3, 3), (64, 32, 3), (33, 512, 1), (256, 384, 3)]:
            w = np.random.default_rng(42).integers(-127, 128, (co, ci, k, k), dtype=np.int8)
            packed = pack_weights(w)
            for m, n, y, x in [(0, 0, 0, 0), (co - 1, ci - 1, k - 1, k - 1), (min(49, co - 1), min(9, ci - 1), 0, k - 1)]:
                offset = (m // 48) * ((ci + 7) // 8) * 48 * 8 * k * k
                offset += ((n // 8) * 4 + m % 4) * 12 * 8 * k * k
                offset += ((m % 48) // 4) * 8 * k * k + (n % 8) * k * k + y * k + x
                self.assertEqual(struct.unpack_from('b', packed, offset)[0], w[m, n, y, x])
            np.testing.assert_array_equal(unpack_weights(packed, co, ci, k), w)

    def test_requant_rounds_away_from_zero_and_saturates(self):
        self.assertEqual(requant(torch.tensor([-255, -3, -1, 1, 3, 255]), 1, 1).tolist(), [-127, -2, -1, 1, 2, 127])
        for ratio in (.1, 1., 2., .000001):
            m, s = coefficients(ratio)
            self.assertAlmostEqual(m / 2**s, ratio, places=9)

    def test_graph_shapes_and_gradients_both_modes(self):
        for channels in (1, 3):
            model = FixedGraph(channels)
            heads = model(torch.rand(1, channels, 224, 224))
            self.assertEqual([list(h.shape) for h in heads], [[1, 33, 7, 7], [1, 33, 14, 14]])
            (heads[0].square().mean() + heads[1].square().mean()).backward()
            self.assertTrue(torch.isfinite(model.layers['0'].weight.grad).all())
            self.assertGreater(model.layers['0'].weight.grad.abs().sum().item(), 0)

    def test_ps_gray_preprocess_matches_pillow_sensor_bytes(self):
        pixels = np.random.default_rng(12).integers(0, 65536, (416, 416), dtype=np.uint16)
        path = OUT / 'sensor.rgb565'; path.write_bytes(pixels.astype('<u2').tobytes())
        r, g, b = pixels >> 11, (pixels >> 5) & 63, pixels & 31
        rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=2).astype(np.uint8)
        for mode in ('GRAY', 'RGB'):
            image = Image.fromarray(rgb).convert('L' if mode == 'GRAY' else 'RGB').resize((224, 224), Image.Resampling.BICUBIC)
            expected = ((np.asarray(image, dtype=np.int32) * 127 + 127) // 255).astype('i1')
            actual = preprocess(path, mode, raw=True).numpy()
            np.testing.assert_array_equal(actual[0] if mode == 'GRAY' else actual.transpose(1, 2, 0), expected)
            (OUT / f'{mode}-input.bin').write_bytes(actual.tobytes())

    def test_original_package_template_still_valid(self):
        validate_payload((ROOT / 'camera/int8/weights.bin').read_bytes(), (ROOT / 'camera/int8/metadata.bin').read_bytes(), 1)
        self.assertEqual(len(pack_weights(np.zeros((32, 3, 3, 3), dtype='i1'))), int(COMMANDS[1, 2]))


if __name__ == '__main__':
    fixtures()
    unittest.main()
