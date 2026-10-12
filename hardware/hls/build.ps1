$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../camera/vivado_env.ps1')
$env:XILINX_VITIS = 'C:/AMDDesignTools/2026.1/Vitis'
$env:PATH = "$env:XILINX_VITIS/bin;$env:XILINX_VITIS/lib/win64.o;$env:PATH"
$taskBuild = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $taskBuild | Out-Null
$taskConfig = @('part=xc7z020clg400-2', '[hls]', 'flow_target=vivado',
                'clock=7', 'syn.top=conv', 'syn.interface.m_axi_addr64=0')
foreach ($taskName in @('top', 'std_conv', 'pwconv', 'maxpool', 'upsample')) {
    $taskSource = (Join-Path $PSScriptRoot "src/$taskName.cpp").Replace('\', '/')
    $taskConfig += "syn.file=$taskSource"
}
$taskConfigPath = Join-Path $taskBuild 'hls_config.cfg'
Set-Content -LiteralPath $taskConfigPath -Value $taskConfig -Encoding ascii
& "$env:XILINX_VITIS/bin/v++.bat" --compile --mode hls --config $taskConfigPath --work_dir (Join-Path $taskBuild 'conv')
if ($LASTEXITCODE) { throw 'Conv HLS build failed' }
