param([int]$IdePort=0)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $taskRoot 'hardware/camera/vivado_env.ps1')
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$env:RDI_APPROOT = $env:XILINX_VITIS
$env:HDI_APPROOT = $env:XILINX_VITIS
$env:RDI_DATADIR = "$env:XILINX_VITIS/data"
$env:RDI_LIBDIR = "$env:XILINX_VITIS/lib/win64.o"
$env:RDI_BINDIR = "$env:XILINX_VITIS/bin"
$env:IDE_SKIP_SERVER_LICENSE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = "$env:XILINX_VITIS/cli;$env:XILINX_VITIS/cli/proto;$env:XILINX_VITIS/cli/python-packages/win64"
$env:PATH = "$env:XILINX_VITIS/lib/win64.o;$env:XILINX_VITIS/tps/win64/python-3.13.0;$env:XILINX_VITIS/tps/win64/cmake-3.24.2/bin;$env:XILINX_VITIS/gnu/aarch32/nt/gcc-arm-none-eabi/bin;$env:XILINX_VITIS/bin;$env:PATH"
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'build') | Out-Null
$taskServer = $null
if ($IdePort) {
    $taskPort = $IdePort
} else {
    $taskPort = 51124
    $taskServer = Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' -ArgumentList @('/d', '/c', 'C:/AMDDesignTools/2026.1/Vitis/bin/vitis-server.bat -p 51124') -RedirectStandardOutput (Join-Path $PSScriptRoot 'build/app_server_stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'build/app_server_stderr.log')
}
try {
    if ($taskServer) { Start-Sleep -Seconds 3 }
    & "$env:XILINX_VITIS/tps/win64/python-3.13.0/python.exe" (Join-Path $PSScriptRoot 'create_app.py') $taskPort
    if ($LASTEXITCODE) { throw 'Vitis application build failed' }
} finally {
    if ($taskServer) {
        $taskProcesses = @(Get-CimInstance Win32_Process)
        $taskOwnedIds = @($taskServer.Id)
        do {
            $taskChildren = @($taskProcesses | Where-Object {
                $_.ParentProcessId -in $taskOwnedIds -and $_.ProcessId -notin $taskOwnedIds
            } | Select-Object -ExpandProperty ProcessId)
            $taskOwnedIds += $taskChildren
        } while ($taskChildren.Count)
        foreach ($taskOwnedId in ($taskOwnedIds | Sort-Object -Descending)) {
            Stop-Process -Id $taskOwnedId -ErrorAction SilentlyContinue
        }
    }
}
