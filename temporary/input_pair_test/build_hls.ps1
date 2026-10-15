$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../../hardware/camera/vivado_env.ps1')
$env:XILINX_VITIS='C:/AMDDesignTools/2026.1/Vitis'
$env:PATH="$env:XILINX_VITIS/bin;$env:XILINX_VITIS/lib/win64.o;$env:PATH"
$taskBuild=Join-Path $PSScriptRoot 'build'
$taskExit=Join-Path $taskBuild 'hls_exit.txt'
if(Test-Path -LiteralPath $taskExit){Remove-Item -LiteralPath $taskExit}
try {
    $taskConfig=@('part=xc7z020clg400-2','[hls]','flow_target=vivado','clock=7','syn.top=conv','syn.interface.m_axi_addr64=0')
    foreach($taskName in @('top','std_conv','maxpool','upsample')) {
        $taskSource=(Join-Path $taskBuild "candidate_src/$taskName.cpp").Replace('\','/')
        $taskConfig+="syn.file=$taskSource"
    }
    $taskCfg=Join-Path $taskBuild 'hls.cfg'
    Set-Content -LiteralPath $taskCfg -Value $taskConfig -Encoding ascii
    & "$env:XILINX_VITIS/bin/v++.bat" --compile --mode hls --config $taskCfg --work_dir (Join-Path $taskBuild 'candidate') *> (Join-Path $taskBuild 'hls.log')
    if($LASTEXITCODE){throw 'Paired input HLS failed'}
    'PASS'|Set-Content -LiteralPath $taskExit
} catch {
    $_|Out-String|Write-Output
    'FAIL'|Set-Content -LiteralPath $taskExit
    exit 1
}
