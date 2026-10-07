param(
    [Parameter(Mandatory=$true)] [string] $GameBin
)
$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "build\Release\d3d11.dll"
if (!(Test-Path $src)) { throw "Overlay DLL not built yet. Run build_msvc_x64.bat first." }
if (!(Test-Path $GameBin)) { throw "Game Bin folder not found: $GameBin" }
$target = Join-Path $GameBin "d3d11.dll"
if (Test-Path $target) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item $target "$target.backup_$stamp" -Force
}
Copy-Item $src $target -Force
Write-Host "Installed TD1 Apex ImGui overlay proxy to $target"
Write-Host "Remove that d3d11.dll to disable the overlay."
