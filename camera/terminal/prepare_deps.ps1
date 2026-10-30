param([string]$Destination = (Join-Path $PSScriptRoot 'build/deps'))
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Destination | Out-Null
$pythonDeps = Join-Path $Destination 'python'
if (!(Test-Path (Join-Path $pythonDeps 'paho/mqtt/client.py'))) {
    $wheel = Join-Path $Destination 'paho_mqtt-2.1.0.whl'
    Invoke-WebRequest 'https://files.pythonhosted.org/packages/c4/cb/00451c3cf31790287768bb12c6bec834f5d292eaf3022afc88e14b8afc94/paho_mqtt-2.1.0-py3-none-any.whl' -OutFile $wheel
    if ((Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant() -ne '6db9ba9b34ed5bc6b6e3812718c7e06e2fd7444540df2455d2c51bd58808feee') { throw 'Paho MQTT checksum mismatch' }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($wheel, $pythonDeps)
}
$dependencies = @(
    @{ Name='json'; Url='https://github.com/nlohmann/json.git'; Tag='v3.12.0'; Commit='55f93686c01528224f448c19128836e7df245f72'; Sparse=@('single_include') },
    @{ Name='httplib'; Url='https://github.com/yhirose/cpp-httplib.git'; Tag='v0.20.1'; Commit='3af7f2c16147f3fbc6e4d717032daf505dc1652c'; Sparse=@() },
    @{ Name='lvgl'; Url='https://github.com/lvgl/lvgl.git'; Tag='v9.4.0'; Commit='c016f72d4c125098287be5e83c0f1abed4706ee5'; Sparse=@('src','env_support') },
    @{ Name='freetype'; Url='https://github.com/freetype/freetype.git'; Tag='VER-2-13-3'; Commit='42608f77f20749dd6ddc9e0536788eaad70ea4b5'; Sparse=@('src','include','builds') }
)
foreach ($dependency in $dependencies) {
    $path = Join-Path $Destination $dependency.Name
    if (!(Test-Path -LiteralPath $path)) {
        & git clone --depth 1 --filter=blob:none --sparse --branch $dependency.Tag $dependency.Url $path
        if ($LASTEXITCODE) { throw "Dependency download failed: $($dependency.Name)" }
    }
    $commit = & git -C $path rev-parse HEAD
    if ($LASTEXITCODE -or $commit -ne $dependency.Commit) { throw "Dependency revision mismatch: $($dependency.Name)" }
    if ($dependency.Sparse.Count) {
        & git -C $path sparse-checkout set @($dependency.Sparse)
        if ($LASTEXITCODE) { throw "Dependency checkout failed: $($dependency.Name)" }
    }
    if ($dependency.Name -eq 'lvgl') {
        # The recovery patch builds on bounds; check it first on repeat runs.
        $recovery = Join-Path $PSScriptRoot 'lvgl-evdev-recovery.patch'
        & git -C $path apply --reverse --check $recovery 2>$null
        if (!$LASTEXITCODE) { continue }
        foreach ($patchName in @('lvgl-evdev-bounds.patch','lvgl-evdev-recovery.patch')) {
            $patch = Join-Path $PSScriptRoot $patchName
            & git -C $path apply --reverse --check $patch 2>$null
            if ($LASTEXITCODE) {
                & git -C $path apply --check $patch
                if ($LASTEXITCODE) { throw 'LVGL mouse patch does not match the pinned source' }
                & git -C $path apply $patch
                if ($LASTEXITCODE) { throw 'LVGL mouse patch failed' }
            }
        }
    }
}
