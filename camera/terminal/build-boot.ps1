param([string]$UbootElf = (Join-Path $PSScriptRoot 'build/delivery/boot/u-boot.elf'), [int]$ServerPort = 51127)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$hardware = Join-Path $root 'hardware/camera/build/terminal'
foreach ($file in @('qualified.dcp','system_wrapper.bit','camera_cnn.xsa')) { if (!(Test-Path -LiteralPath (Join-Path $hardware $file))) { throw "Missing qualified terminal hardware: $file" } }
$uboot = (Resolve-Path -LiteralPath $UbootElf).Path
$header = [IO.File]::ReadAllBytes($uboot)
if ($header[0] -ne 127 -or $header[1] -ne 69 -or $header[2] -ne 76 -or $header[3] -ne 70 -or $header[4] -ne 1 -or [BitConverter]::ToUInt16($header,18) -ne 40) { throw 'An ARM32 U-Boot ELF is required' }
if (Get-NetTCPConnection -LocalPort $ServerPort -State Listen -ErrorAction SilentlyContinue) { throw "Vitis server port $ServerPort is already in use" }
. (Join-Path $root 'hardware/camera/vivado_env.ps1')
$vitisRoot = 'C:/AMDDesignTools/2026.1/Vitis'
$env:XILINX_VITIS=$vitisRoot
$env:RDI_APPROOT=$vitisRoot
$env:HDI_APPROOT=$vitisRoot
$env:RDI_DATADIR="$vitisRoot/data"
$env:RDI_LIBDIR="$vitisRoot/lib/win64.o"
$env:RDI_BINDIR="$vitisRoot/bin"
$env:IDE_SKIP_SERVER_LICENSE='1'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH="$vitisRoot/cli;$vitisRoot/cli/proto;$vitisRoot/cli/python-packages/win64"
$env:PATH="$vitisRoot/lib/win64.o;$vitisRoot/tps/win64/python-3.13.0;$vitisRoot/gnu/aarch32/nt/gcc-arm-none-eabi/bin;$vitisRoot/bin;$env:PATH"
$output=Join-Path $PSScriptRoot 'build/delivery/boot'
New-Item -ItemType Directory -Force $output | Out-Null
$server=Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' -ArgumentList @('/d','/c',"$vitisRoot/bin/vitis-server.bat -p $ServerPort") -RedirectStandardOutput (Join-Path $PSScriptRoot 'build/boot-server.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'build/boot-server.stderr.log')
try {
    Start-Sleep -Seconds 3
    & "$vitisRoot/tps/win64/python-3.13.0/python.exe" (Join-Path $PSScriptRoot 'create_platform.py') $ServerPort
    if ($LASTEXITCODE) { throw 'Terminal FSBL build failed' }
    $fsbl=Join-Path $PSScriptRoot 'build/vitis/vision_terminal_platform/zynq_fsbl/build/fsbl.elf'
    $bit=Join-Path $hardware 'system_wrapper.bit'
    $bif=Join-Path $PSScriptRoot 'build/terminal-sd.bif'
    @"
terminal_sd:
{
    [bootloader] $($fsbl.Replace('\','/'))
    $($bit.Replace('\','/'))
    $($uboot.Replace('\','/'))
}
"@ | Set-Content -LiteralPath $bif -Encoding ascii
    & "$vitisRoot/bin/unwrapped/win64.o/bootgen.exe" -arch zynq -image $bif -o (Join-Path $output 'BOOT.bin') -w on
    if ($LASTEXITCODE) { throw 'Terminal SD boot image generation failed' }
    Write-Output "Terminal SD boot image: $(Join-Path $output 'BOOT.bin')"
} finally {
    $processes=@(Get-CimInstance Win32_Process)
    $owned=@($server.Id)
    do {
        $children=@($processes | Where-Object { $_.ParentProcessId -in $owned -and $_.ProcessId -notin $owned } | Select-Object -ExpandProperty ProcessId)
        $owned+=$children
    } while ($children.Count)
    foreach ($taskPid in ($owned | Sort-Object -Descending)) { Stop-Process -Id $taskPid -ErrorAction SilentlyContinue }
}
