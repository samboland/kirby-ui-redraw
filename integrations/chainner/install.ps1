param([string]$ResourcesPath)
$ErrorActionPreference = 'Stop'
if (-not $ResourcesPath) {
    $installed = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'chaiNNer') -Directory -Filter 'app-*' |
        Sort-Object { [version]($_.Name -replace '^app-', '') } -Descending | Select-Object -First 1
    if (-not $installed) { throw 'chaiNNer installation not found. Supply -ResourcesPath.' }
    $ResourcesPath = Join-Path $installed.FullName 'resources/src'
}
$targetFolder = Join-Path $ResourcesPath 'packages/chaiNNer_standard/image_filter/blur'
if (-not (Test-Path (Join-Path $targetFolder 'gaussian_blur.py'))) {
    throw 'Unsupported chaiNNer layout. No changes made.'
}
$source = Join-Path $PSScriptRoot 'mean_curvature_blur.py'
$target = Join-Path $targetFolder 'mean_curvature_blur.py'
if ((Test-Path $target) -and ((Get-FileHash $target).Hash -ne (Get-FileHash $source).Hash)) {
    Copy-Item -LiteralPath $target -Destination ($target + '.backup-' + (Get-Date -Format 'yyyyMMddHHmmss'))
}
Copy-Item -LiteralPath $source -Destination $target
Write-Output "Installed $target"
Write-Output 'Save your chain and restart chaiNNer. Search for Mean Curvature Blur (GIMP).'
