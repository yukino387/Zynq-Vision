param([string]$BoardConstraints = (Join-Path $PSScriptRoot 'navigator-v3.9.xdc'))
$ErrorActionPreference = 'Stop'
$pinFile = (Resolve-Path -LiteralPath $BoardConstraints).Path
$previous = $env:VISION_HDMI_XDC
try {
    $env:VISION_HDMI_XDC = $pinFile
    & (Join-Path $PSScriptRoot '../camera/build.ps1')
    if ($LASTEXITCODE) { throw 'Terminal display hardware build failed' }
} finally {
    if ($null -eq $previous) { Remove-Item Env:VISION_HDMI_XDC -ErrorAction SilentlyContinue }
    else { $env:VISION_HDMI_XDC = $previous }
}
