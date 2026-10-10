param(
    [Parameter(Mandatory=$true)] [string] $GameBin,
    [string] $Python = 'python',
    [switch] $Install
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-GameClosed {
    $gameProcesses = @(Get-Process | Where-Object {
        $_.ProcessName -in @('TS4_x64', 'TS4_DX9_x64', 'TS4', 'TS4_Launcher_x64')
    })
    if ($gameProcesses.Count -ne 0) {
        throw 'Close The Sims 4 normally before checking/installing the overlay. No process will be killed.'
    }
}

function Resolve-UnlinkedPath([string] $Path) {
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).ProviderPath
    $entry = Get-Item -LiteralPath $resolved -Force
    while ($null -ne $entry) {
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Linked/junction installation paths are not supported: $($entry.FullName)"
        }
        if ($entry -is [IO.FileInfo]) { $entry = $entry.Directory } else { $entry = $entry.Parent }
    }
    return $resolved
}

Assert-GameClosed
$binPath = Resolve-UnlinkedPath $GameBin
if (-not (Test-Path -LiteralPath $binPath -PathType Container)) { throw 'Game Bin must be a directory.' }
$exePath = Resolve-UnlinkedPath (Join-Path $binPath 'TS4_x64.exe')
$sourcePath = Resolve-UnlinkedPath (Join-Path $PSScriptRoot 'build\Release\d3d11.dll')
$targetPath = [IO.Path]::GetFullPath((Join-Path $binPath 'd3d11.dll'))
if ([IO.Path]::GetDirectoryName($targetPath) -ne $binPath) { throw 'Target escaped the verified Game Bin directory.' }
if (Test-Path -LiteralPath $targetPath) {
    throw 'd3d11.dll already exists. Refusing to replace any Apex, ReShade, GShade or other proxy.'
}
$verification = & $Python (Join-Path $PSScriptRoot 'verify_ts4_dx11_imports.py') $exePath
if ($LASTEXITCODE -ne 0) { throw 'Executable import verification failed. No game file was written.' }
$proof = ($verification -join "`n") | ConvertFrom-Json
if (-not $proof.ok) { throw 'Executable verifier did not return an affirmative result.' }
$sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$exeHash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($exeHash -ne $proof.sha256) { throw 'Game executable changed during verification. No game file was written.' }
$record = [ordered]@{
    schema = 1; installed = $false; executable = $exePath; executable_sha256 = $exeHash
    proxy_source = $sourcePath; proxy_sha256 = $sourceHash; target = $targetPath
    import_proof = $proof; runtime_compatibility_proven = $false
}
if (-not $Install) {
    $record | ConvertTo-Json -Depth 8
    Write-Host 'Check only. Explicit -Install is required to copy a verified proxy; live compatibility still requires proof.'
    return
}
Assert-GameClosed
if ((Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $exeHash -or
    (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceHash) {
    throw 'An installation input changed. No game file was written.'
}
$recordPath = Join-Path $PSScriptRoot ('build\install-record-' + [guid]::NewGuid().ToString('N') + '.json')
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding UTF8
# File.Copy(false) refuses collisions even after preflight; never replace another owner.
[IO.File]::Copy($sourcePath, $targetPath, $false)
if ((Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceHash) {
    throw "Copied file verification failed. Preserved target for inspection; record: $recordPath"
}
$record.installed = $true
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding UTF8
Write-Host "Installed verified Apex proxy. Installation record: $recordPath"
