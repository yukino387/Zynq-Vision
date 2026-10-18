"""GPU training-step throughput; excludes file loading, preprocessing and PTQ."""
import gc
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'camera/training'))
from pl_model import FixedGraph
from detection import loss

torch.set_num_threads(4)
torch.use_deterministic_algorithms(False)
torch.backends.cudnn.benchmark = False
assert torch.cuda.is_available(), 'GPU benchmark requires CUDA PyTorch'


def measure(channels, batch, amp):
    torch.manual_seed(7020)
    model = FixedGraph(channels).to(device='cuda', memory_format=torch.channels_last).train()
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    images = torch.rand(batch, channels, 224, 224, device='cuda').contiguous(memory_format=torch.channels_last)
    boxes = [torch.tensor([[0., .1, .1, .3, .3]]) for _ in range(batch)]
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler('cuda', enabled=amp and dtype == torch.float16)
    torch.cuda.reset_peak_memory_stats()

    def step():
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast('cuda', dtype=dtype, enabled=amp):
            value = loss(model(images), boxes)
        scaler.scale(value).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10.)
        scaler.step(optimizer)
        scaler.update()
        return float(value.detach())

    for _ in range(3):
        step()
    times = []
    for _ in range(12):
        torch.cuda.synchronize()
        started = time.perf_counter()
        last_loss = step()
        torch.cuda.synchronize()
        times.append(time.perf_counter() - started)
    result = {'mode': 'GRAY' if channels == 1 else 'RGB', 'batchSize': batch,
              'precision': str(dtype) if amp else 'torch.float32',
              'meanStepMs': statistics.mean(times) * 1000, 'medianStepMs': statistics.median(times) * 1000,
              'imagesPerSecond': batch / statistics.mean(times),
              'peakAllocatedMiB': torch.cuda.max_memory_allocated() / 2**20,
              'lastLoss': last_loss, 'warmupSteps': 3, 'measuredSteps': 12, 'memoryFormat': 'channels_last'}
    print(json.dumps(result), flush=True)
    return result


results = []
for channels in (1, 3):
    for batch, amp in ((16, False), (16, True), (32, True)):
        results.append(measure(channels, batch, amp))
        gc.collect()
        torch.cuda.empty_cache()
report = {'gpu': torch.cuda.get_device_name(0), 'torch': torch.__version__, 'cuda': torch.version.cuda,
          'scope': 'Synthetic preloaded tensors. Includes forward, detection loss, backward, gradient clipping and Adam update. Excludes loading/preprocessing, validation, INT8 export.',
          'results': results}
(Path(__file__).parent / 'gpu_benchmark_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
