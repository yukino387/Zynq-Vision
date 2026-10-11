$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'build/sim') | Out-Null
Push-Location (Join-Path $PSScriptRoot 'build/sim')
try {
    $taskBin = "$env:XILINX_VIVADO/bin/unwrapped/win64.o"
    & "$taskBin/xvlog.exe" -sv "$env:XILINX_VIVADO/data/verilog/src/glbl.v" "$env:XILINX_VIVADO/data/ip/xpm/xpm_cdc/hdl/xpm_cdc.sv" "$env:XILINX_VIVADO/data/ip/xpm/xpm_memory/hdl/xpm_memory.sv" "$env:XILINX_VIVADO/data/ip/xpm/xpm_fifo/hdl/xpm_fifo.sv" (Join-Path $taskRoot 'hardware/camera/ov5640_capture.v') (Join-Path $PSScriptRoot 'capture_tb.sv')
    if ($LASTEXITCODE) { throw 'RTL compilation failed' }
    & "$taskBin/xelab.exe" capture_tb glbl -s capture_test
    if ($LASTEXITCODE) { throw 'RTL elaboration failed' }
    & "$taskBin/xsim.exe" capture_test -runall
    if ($LASTEXITCODE) { throw 'RTL simulation failed' }
} finally { Pop-Location }
