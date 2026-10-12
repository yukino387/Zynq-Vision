from pathlib import Path
import numpy as np
from PIL import Image

test = Path(__file__).resolve().parent
root = test.parents[1]
image = Image.open(root / 'temporary/image_inference_test/street.jpg').convert('RGB')
pixels = np.asarray(image.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / np.float32(255)
values = np.floor(pixels * np.float32(512) + np.float32(.5)).astype('<i2').transpose(2, 0, 1).copy()
folder = test / 'build/fixed_files'
folder.mkdir(parents=True, exist_ok=True)
values.tofile(folder / 'input.bin')
hashed = 2166136261
for value in values.tobytes():
    hashed = ((hashed ^ value) * 16777619) & 0xffffffff
(test / 'input_expected.h').write_text(
    f'constexpr unsigned INPUT_HASH={hashed}u;\nconstexpr int INPUT_MIN={values.min()}, INPUT_MAX={values.max()};\n',
    encoding='utf-8')
