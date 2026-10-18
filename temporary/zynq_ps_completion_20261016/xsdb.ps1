param([Parameter(Mandatory=$true)][string]$Script)
$ErrorActionPreference = 'Stop'
. 'C:/00_workplace/fpga/cnn_accelerator/hardware/camera/vivado_env.ps1'
$env:XILINX_VITIS='C:/AMDDesignTools/2026.1/Vitis'
$env:RDI_APPROOT=$env:XILINX_VITIS
$env:HDI_APPROOT=$env:XILINX_VITIS
$env:RDI_DATADIR="$env:XILINX_VITIS/data"
$env:RDI_LIBDIR="$env:XILINX_VITIS/lib/win64.o"
$env:RDI_BINDIR="$env:XILINX_VITIS/bin"
$env:PATH="$env:RDI_LIBDIR;$env:XILINX_VITIS/bin;$env:PATH"
& "$env:XILINX_VITIS/bin/unwrapped/win64.o/xsdb.exe" $Script
if ($LASTEXITCODE) { throw 'XSDB operation failed' }
