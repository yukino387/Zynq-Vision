$ErrorActionPreference = 'Stop'
$output = Join-Path $PSScriptRoot 'build/delivery'
$prefix = Join-Path $output 'rootfs'
New-Item -ItemType Directory -Force (Join-Path $prefix 'usr/local/bin'),(Join-Path $prefix 'usr/share/vision'),(Join-Path $prefix 'etc/systemd/system'),(Join-Path $prefix 'var/lib/vision/jobs'),(Join-Path $output 'licenses'),(Join-Path $output 'kernel') | Out-Null
foreach ($name in @('vision-engine','vision-panel')) {
    $source = Join-Path $PSScriptRoot "build/arm/$name"
    $header = [System.IO.File]::ReadAllBytes($source)
    if ($header[0] -ne 127 -or $header[1] -ne 69 -or $header[2] -ne 76 -or $header[3] -ne 70 -or [BitConverter]::ToUInt16($header,18) -ne 40) { throw "Not an ARM ELF: $name" }
    Copy-Item -LiteralPath $source -Destination (Join-Path $prefix "usr/local/bin/$name")
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install_job.py') -Destination (Join-Path $prefix 'usr/local/bin/vision-install-job.py')
foreach ($name in @('vision-engine.service','vision-panel.service')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot "linux/$name") -Destination (Join-Path $prefix 'etc/systemd/system') }
foreach ($name in @('vision_accel.c','vision_fb.c','vision_uapi.h','Makefile','vision-pl.dtsi','navigator-v3.9.dts','navigator-v3.9-usb.dtsi','kernel.config','uboot.config','build-kernel.sh','build-uboot.sh','build-modules.sh','build-rootfs.sh','build-initramfs.sh','build-sd-image.sh','install-rootfs.sh','rcS','inittab')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot "linux/$name") -Destination (Join-Path $output 'kernel') }
$fontRoot = 'https://raw.githubusercontent.com/notofonts/noto-cjk/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans'
$font = Join-Path $prefix 'usr/share/vision/NotoSansCJKsc-Regular.otf'
if (!(Test-Path -LiteralPath $font)) { Invoke-WebRequest -Uri "$fontRoot/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" -OutFile $font }
if ((Get-FileHash -LiteralPath $font -Algorithm SHA256).Hash.ToLowerInvariant() -ne '2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b') { throw 'Chinese font checksum mismatch' }
Invoke-WebRequest -Uri "$fontRoot/LICENSE" -OutFile (Join-Path $output 'licenses/Noto-CJK-OFL.txt')
$licenses = @(
    @('lvgl/LICENCE.txt','LVGL.txt'), @('json/LICENSE.MIT','nlohmann-json.txt'),
    @('httplib/LICENSE','cpp-httplib.txt'), @('freetype/LICENSE.TXT','FreeType.txt')
)
foreach ($license in $licenses) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot "build/deps/$($license[0])") -Destination (Join-Path $output "licenses/$($license[1])") }
$ftLicense = & git -C (Join-Path $PSScriptRoot 'build/deps/freetype') show HEAD:docs/FTL.TXT
if ($LASTEXITCODE) { throw 'Cannot read FreeType license' }
[System.IO.File]::WriteAllLines((Join-Path $output 'licenses/FreeType-FTL.txt'), $ftLicense, [System.Text.UTF8Encoding]::new($false))
$manifest = @{ formatVersion=1; target='Zynq-7020 ARM Linux hard-float'; qualification='Cross-compiled; hardware commissioning required'; files=@() }
foreach ($file in Get-ChildItem -LiteralPath $output -File -Recurse) {
    if ($file.Name -eq 'checksums.json') { continue }
    $manifest.files += @{ path=[System.IO.Path]::GetRelativePath($output,$file.FullName).Replace('\','/'); size=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
[System.IO.File]::WriteAllText((Join-Path $output 'checksums.json'),($manifest | ConvertTo-Json -Depth 6),[System.Text.UTF8Encoding]::new($false))
Write-Output "Terminal payload packaged: $output"
