param([string]$Version = "")
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (!$Version) {
    $Version = (& git -C $root describe --tags --always --dirty 2>$null)
    if ($LASTEXITCODE -or !$Version) { $Version = 'fw-' + (Get-Date -Format 'yyyyMMdd-HHmmss') }
}
$Version = $Version.Trim()
if ($Version.Length -gt 55 -or $Version -match '[^\x20-\x7e]') {
    throw 'Firmware version must be 1..55 printable ASCII bytes'
}
$out = Join-Path $PSScriptRoot 'build/firmware'
New-Item -ItemType Directory -Force $out | Out-Null
@"
#pragma once
#define FIRMWARE_VERSION "$Version"
"@ | Set-Content -LiteralPath (Join-Path $out 'firmware_version.h') -Encoding ascii

& (Join-Path $PSScriptRoot 'build_app.ps1')
if ($LASTEXITCODE) { throw 'Application build failed' }
$elf = Join-Path $root 'vitis_live/camera_live/build/camera_live.elf'
if (!(Test-Path -LiteralPath $elf)) { throw "Missing app ELF: $elf" }
& python (Join-Path $PSScriptRoot 'pack_firmware.py') --elf $elf --version $Version --output $out
if ($LASTEXITCODE) { throw 'Firmware packaging failed' }
Write-Output "Firmware package ready under $out (version $Version)"
