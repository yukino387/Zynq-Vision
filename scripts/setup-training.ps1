$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$trainingEnv = Join-Path $projectRoot 'data/training-venv'
$trainingPython = Join-Path $trainingEnv 'Scripts/python.exe'
if (!(Test-Path -LiteralPath $trainingPython)) {
    uv venv --python 3.12 $trainingEnv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create training environment' }
}
uv pip install --python $trainingPython -r (Join-Path $projectRoot 'camera/training/requirements-cuda.txt')
if ($LASTEXITCODE -ne 0) { throw 'Failed to install CUDA training dependencies' }
& $trainingPython -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable; training requires an NVIDIA GPU and driver'; print(torch.__version__); print(torch.cuda.get_device_name(0)); print('CUDA training environment ready')"
if ($LASTEXITCODE -ne 0) { throw 'CUDA runtime verification failed' }
