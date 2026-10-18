from pathlib import Path
p=Path('camera/build_boot.ps1');s=p.read_text(encoding='utf-8');s=s.replace('param([switch]$Flash)','param([switch]$Flash, [int]$TargetId = 3)');s=s.replace('''    & "$env:XILINX_VITIS/bin/program_flash.bat" -f $boot -offset 0 -flash_type qspi-x4-single -fsbl $fsbl -blank_check -verify -cable type xilinx_tcf url TCP:127.0.0.1:3121
    if ($LASTEXITCODE) { throw 'QSPI programming or verification failed' }''','''    $flashOutput = & "$env:XILINX_VITIS/bin/program_flash.bat" -f $boot -offset 0 -flash_type qspi-x4-single -fsbl $fsbl -blank_check -verify -target_id $TargetId -url tcp:127.0.0.1:3121 2>&1
    $flashExit = $LASTEXITCODE
    $flashOutput | Write-Output
    if ($flashExit -or ($flashOutput -match 'ERROR:') -or -not ($flashOutput -match 'Flash Operation Successful')) { throw 'QSPI programming or verification failed' }''');p.write_bytes(s.encode('utf-8'))
