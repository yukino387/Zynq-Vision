"""One real training job. Progress is JSONL on stdout; errors go to stderr."""
import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import numpy as np
import torch
from torch.utils.data import DataLoader

from data import Samples, collate
from detection import loss, decode, metrics
from pl_model import FixedGraph, HEADS, OUTPUT_SCALES, export_int8, integer_forward


def progress(stage, percent, **details):
    print(json.dumps({'stage': stage, 'progress': percent, **details}, allow_nan=False), flush=True)


def run(spec, directory):
    options = spec['options']
    seed = options['seed']
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.set_num_threads(options.get('threads', 4))
    device = torch.device(options.get('device', 'cuda'))
    if device.type == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA unavailable. Run scripts/setup-training.ps1 and configure TRAINING_PYTHON to use data/training-venv/Scripts/python.exe')
    use_cuda = device.type == 'cuda'
    torch.use_deterministic_algorithms(not use_cuda)
    torch.backends.cudnn.benchmark = False
    amp = use_cuda and options.get('amp', True)
    amp_dtype = torch.bfloat16 if use_cuda and torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler('cuda', enabled=amp and amp_dtype == torch.float16)
    workers = options.get('workers', 4)
    runtime = {'device': str(device), 'deviceName': torch.cuda.get_device_name(0) if use_cuda else 'CPU',
               'torch': torch.__version__, 'precision': str(amp_dtype) if amp else 'torch.float32', 'workers': workers}
    image_options = {'device': device, 'non_blocking': use_cuda,
                     'memory_format': torch.channels_last if use_cuda else torch.contiguous_format}
    runtime['memoryFormat'] = 'channels_last' if use_cuda else 'contiguous'
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    items = spec['items']
    if len({item['id'] for item in items}) != len(items):
        raise ValueError('Duplicate sample in frozen dataset')
    if any(item['split'] not in ('train', 'val', 'test') for item in items):
        raise ValueError('Supported dataset splits: train, val, test')
    train = [item for item in items if item['split'] == 'train']
    val = [item for item in items if item['split'] == 'val']
    if not val:
        if len(train) < 2:
            raise ValueError('At least two training samples or an explicit validation split are required')
        shuffled = sorted(train, key=lambda item: item['id'])
        random.Random(seed).shuffle(shuffled)
        cut = max(1, math.floor(len(shuffled) * .2))
        val, train = shuffled[:cut], shuffled[cut:]
    if not train:
        raise ValueError('Training split is empty')
    directory.mkdir(parents=True, exist_ok=True)
    progress('Loading Samples', 3, runtime=runtime)
    train_data, val_data = Samples(train, options['colorMode']), Samples(val, options['colorMode'])
    loader_options = {'num_workers': workers, 'pin_memory': use_cuda, 'persistent_workers': workers > 0, 'collate_fn': collate}
    loader = DataLoader(train_data, batch_size=options['batchSize'], shuffle=True, generator=torch.Generator().manual_seed(seed), **loader_options)
    validation = DataLoader(val_data, batch_size=options['batchSize'], **loader_options)
    model = FixedGraph(1 if options['colorMode'] == 'GRAY' else 3).to(device=device, memory_format=image_options['memory_format'])
    optimizer = torch.optim.Adam(model.parameters(), lr=options['learningRate'])
    best, history = math.inf, []
    for epoch in range(options['epochs']):
        model.train()
        if use_cuda:
            torch.cuda.synchronize()
        epoch_started = time.perf_counter()
        training_loss = 0.
        for step, (images, boxes) in enumerate(loader):
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=amp_dtype, enabled=amp):
                value = loss(model(images.to(**image_options)), boxes)
            if not torch.isfinite(value):
                raise ValueError('Non-finite training loss')
            scaler.scale(value).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10., error_if_nonfinite=not scaler.is_enabled())
            scaler.step(optimizer)
            scaler.update()
            training_loss += value.item() * len(images)
            progress('Training', 5 + int(65 * (epoch + (step + 1) / len(loader)) / options['epochs']), epoch=epoch + 1, epochs=options['epochs'], loss=value.item())
        model.eval()
        if use_cuda:
            torch.cuda.synchronize()
        training_seconds = time.perf_counter() - epoch_started
        validation_started = time.perf_counter()
        validation_loss = 0.
        with torch.inference_mode():
            for images, boxes in validation:
                with torch.autocast('cuda', dtype=amp_dtype, enabled=amp):
                    validation_loss += loss(model(images.to(**image_options)), boxes).item() * len(images)
        if use_cuda:
            torch.cuda.synchronize()
        validation_loss /= len(val_data)
        if not math.isfinite(validation_loss):
            raise ValueError('Non-finite validation loss')
        history.append({'epoch': epoch + 1, 'trainLoss': training_loss / len(train_data), 'valLoss': validation_loss,
                        'trainSeconds': training_seconds, 'validationSeconds': time.perf_counter() - validation_started,
                        'imagesPerSecond': len(train_data) / training_seconds})
        if validation_loss < best:
            best = validation_loss
        progress('Validation', 5 + int(65 * (epoch + 1) / options['epochs']), **history[-1])
    # Save the LAST epoch, not the best-val epoch: the held-out split is a harder
    # background set, and the early best checkpoint is underfit.
    torch.save({'state_dict': model.state_dict(), 'options': options, 'epoch': options['epochs']}, directory / 'checkpoint.pt')
    checkpoint = torch.load(directory / 'checkpoint.pt', weights_only=True, map_location='cpu')
    model.eval()
    model.load_state_dict(checkpoint['state_dict'])
    progress('Quantization', 72)
    maximum = 0.

    def observe(index, value):
        nonlocal maximum
        if index not in HEADS:
            maximum = max(maximum, value.abs().max().item())

    # All hidden/concat branches use one symmetric scale; output scales stay fixed
    # because all existing consumers decode those two constants.
    with torch.inference_mode():
        for images, _ in loader:
            model(images.to(**image_options), observe)
    hidden_scale = max(maximum / 127, 1e-6)
    weights, metadata, manifest = export_int8(model, hidden_scale, spec['version'], directory)
    if spec.get('classes'):
        classes = spec['classes']
        if len(classes) != 6 or len(set(classes)) != 6 or any(not isinstance(c, str) or not c.strip() or len(c) > 40 for c in classes):
            raise ValueError('Model requires six unique class slots')
        manifest['classes'] = classes
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if use_cuda:
        runtime['peakAllocatedMiB'] = torch.cuda.max_memory_allocated() / 2**20
    model = model.cpu()
    progress('Validation', 85)
    predictions, labels = [], []
    for index, (images, boxes) in enumerate(DataLoader(val_data, batch_size=1, collate_fn=collate)):
        integer = integer_forward(model, torch.round(images * 127), weights, metadata)
        outputs = [value[0].float() * scale for value, scale in zip(integer, OUTPUT_SCALES)]
        predictions.append(decode(outputs)); labels.append(boxes[0])
        progress('Validation', 85 + int(12 * (index + 1) / len(val_data)))
    report = {'options': options, 'runtime': runtime, 'elapsedSeconds': time.perf_counter() - started,
              'bestEpoch': min(history, key=lambda h: h['valLoss'])['epoch'],
              'bestValidationLoss': best,
              'lastEpoch': checkpoint['epoch'], 'lastValidationLoss': history[-1]['valLoss'],
              'history': history, 'hiddenScale': hidden_scale, 'metrics': metrics(predictions, labels),
              'split': {'train': [item['id'] for item in train], 'val': [item['id'] for item in val]},
              'datasetChecksum': spec['datasetChecksum'], 'manifest': manifest}
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    progress('Packaging', 99)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        run(json.loads(args.spec.read_text(encoding='utf-8')), args.output)
    except Exception as error:
        print(str(error), file=sys.stderr, flush=True)
        raise
