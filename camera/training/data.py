"""Frozen dataset loader, with sensor RGB565 and PS two-pass resize arithmetic."""
import hashlib
import re
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parents[2]
COEFFICIENTS = [(int(start), int(count), np.array([int(v) for v in values.split(',')], dtype=np.int64))
                for start, count, values in re.findall(r'\{(\d+),(\d+),\{([^}]+)\}\}', (ROOT / 'camera/int8/gray_coefficients.h').read_text())]
if len(COEFFICIENTS) != 224:
    raise ValueError('PS resize table requires 224 entries')


def preprocess(path, mode, raw=False):
    if raw:
        pixels = np.frombuffer(Path(path).read_bytes(), dtype='<u2')
        if pixels.size != 416 * 416:
            raise ValueError('RGB565 asset must be exactly 416x416')
        pixels = pixels.reshape(416, 416)
        r, g, b = pixels >> 11, (pixels >> 5) & 63, pixels & 31
    else:
        with Image.open(path) as image:
            rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB').resize((416, 416), Image.Resampling.BICUBIC), dtype=np.uint16)
        r, g, b = rgb[:, :, 0] >> 3, rgb[:, :, 1] >> 2, rgb[:, :, 2] >> 3
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=2).astype(np.int64)
    values = ((rgb[:, :, 0] * 19595 + rgb[:, :, 1] * 38470 + rgb[:, :, 2] * 7471 + 32768) >> 16)[:, :, None] if mode == 'GRAY' else rgb
    horizontal = np.empty((416, 224, values.shape[2]), dtype=np.int64)
    for x, (start, count, coefficients) in enumerate(COEFFICIENTS):
        horizontal[:, x] = ((values[:, start:start + count] * coefficients[None, :count, None]).sum(1) + (1 << 21)) >> 22
    horizontal = horizontal.clip(0, 255)
    output = np.empty((224, 224, values.shape[2]), dtype=np.int64)
    for y, (start, count, coefficients) in enumerate(COEFFICIENTS):
        output[y] = ((horizontal[start:start + count] * coefficients[:count, None, None]).sum(0) + (1 << 21)) >> 22
    return torch.from_numpy(((output.clip(0, 255) * 127 + 127) // 255).transpose(2, 0, 1).astype('i1').copy())


class Samples(Dataset):
    def __init__(self, items, mode):
        self.items, self.mode = items, mode
        for item in items:
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Frozen dataset asset checksum mismatch')
            if item['width'] <= 0 or item['height'] <= 0:
                raise ValueError('Invalid frozen image dimensions')
            if not item.get('raw', False):
                with Image.open(item['path']) as image:
                    if ImageOps.exif_transpose(image).size != (item['width'], item['height']):
                        raise ValueError('Frozen annotation dimensions do not match image')
            for box in item['boxes']:
                if not isinstance(box['classId'], int) or not 0 <= box['classId'] < 6 or not (0 <= box['x1'] < box['x2'] <= item['width'] and 0 <= box['y1'] < box['y2'] <= item['height']):
                    raise ValueError('Box outside fixed six-class detector contract')

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        item = self.items[index]
        x = preprocess(item['path'], self.mode, item.get('raw', False))
        boxes = torch.tensor([[b['classId'], b['x1'] / item['width'], b['y1'] / item['height'], b['x2'] / item['width'], b['y2'] / item['height']] for b in item['boxes']], dtype=torch.float32).reshape(-1, 5)
        return x.float() / 127, boxes


def collate(batch):
    return torch.stack([b[0] for b in batch]), [b[1] for b in batch]
