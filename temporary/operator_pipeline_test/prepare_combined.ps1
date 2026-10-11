$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& python (Join-Path $PSScriptRoot 'prepare_phase64.py')
if ($LASTEXITCODE) { throw 'Channel tiling preparation failed' }
$env:TILE_SOURCE = Join-Path $PSScriptRoot 'build/phase64_src'
$env:TILE_OUTPUT = 'combined_src'
try {
    & python (Join-Path $PSScriptRoot 'prepare_tile26.py')
    if ($LASTEXITCODE) { throw 'Spatial tiling preparation failed' }
} finally {
    Remove-Item Env:TILE_SOURCE,Env:TILE_OUTPUT
}
$taskTop = Join-Path $PSScriptRoot 'build/combined_src/top.cpp'
$taskText = [IO.File]::ReadAllText($taskTop)
$taskText = $taskText.Replace('max_read_burst_length=256', 'max_read_burst_length=256 num_read_outstanding=4')
[IO.File]::WriteAllText($taskTop, $taskText, [Text.UTF8Encoding]::new($false))
