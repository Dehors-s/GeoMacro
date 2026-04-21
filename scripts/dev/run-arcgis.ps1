param(
    [switch]$BuildFirst,
    [string]$Configuration = "Debug",
    [string]$ArcGISProInstallDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ArcGISProInstallDir {
    param([string]$OverridePath)

    if ($OverridePath -and (Test-Path $OverridePath)) {
        return ((Resolve-Path $OverridePath).Path).TrimEnd('\\')
    }

    $candidates = @()

    try {
        $reg64 = Get-ItemProperty -Path "HKLM:\SOFTWARE\ESRI\ArcGISPro" -ErrorAction Stop
        $candidates += $reg64.InstallDir
    } catch {}

    try {
        $reg32 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\ESRI\ArcGISPro" -ErrorAction Stop
        $candidates += $reg32.InstallDir
    } catch {}

    $candidates += @(
        "C:\Program Files\ArcGIS\Pro",
        "D:\Program Files\ArcGIS\Pro",
        "D:\ArcGIS Pro 3.0",
        "D:\ArcGIS\Pro",
        "E:\ArcGIS\Pro"
    )

    $resolved = $candidates |
        Where-Object { $_ -and (Test-Path $_) } |
        Select-Object -First 1

    if (-not $resolved) {
        throw "ArcGIS Pro install directory not found. Pass -ArcGISProInstallDir explicitly."
    }

    return ((Resolve-Path $resolved).Path).TrimEnd('\\')
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
if ($BuildFirst) {
    & (Join-Path $PSScriptRoot "build-addin.ps1") -Configuration $Configuration -ArcGISProInstallDir $ArcGISProInstallDir
}

$arcgisDir = Resolve-ArcGISProInstallDir -OverridePath $ArcGISProInstallDir
$arcgisExe = Join-Path $arcgisDir "bin\ArcGISPro.exe"
if (-not (Test-Path $arcgisExe)) {
    throw "ArcGISPro.exe not found: $arcgisExe"
}

Write-Host "Launching ArcGIS Pro: $arcgisExe"
Start-Process -FilePath $arcgisExe -WorkingDirectory (Split-Path -Parent $arcgisExe)

Write-Host "ArcGIS Pro started. Open GeoMacro tab and check Event Log panel to verify Commit 1 behavior."
