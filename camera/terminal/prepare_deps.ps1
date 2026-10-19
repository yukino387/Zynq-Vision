param([string]$Destination = (Join-Path $PSScriptRoot 'build/deps'))
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Destination | Out-Null
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
        $patch = Join-Path $PSScriptRoot 'lvgl-evdev-bounds.patch'
        & git -C $path apply --reverse --check $patch 2>$null
        if ($LASTEXITCODE) {
            & git -C $path apply --check $patch
            if ($LASTEXITCODE) { throw 'LVGL mouse patch does not match the pinned source' }
            & git -C $path apply $patch
            if ($LASTEXITCODE) { throw 'LVGL mouse patch failed' }
        }
    }
}
