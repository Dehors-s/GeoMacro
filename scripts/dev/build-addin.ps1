param(
    [string]$Configuration = "Debug",
    [string]$ArcGISProInstallDir = "",
    [string]$ProjectPath = "addins/GeoMacroAddin/GeoMacroAddin.csproj"
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

function Resolve-DefaultAssemblyName {
    param([string]$ConfigPath)

    if (-not (Test-Path $ConfigPath)) {
        return "GeoMacroAddin.dll"
    }

    [xml]$xml = Get-Content $ConfigPath -Encoding UTF8
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("d", "http://schemas.esri.com/DADF/Registry")

    $arcNode = $xml.SelectSingleNode("/d:ArcGIS", $ns)
    if (-not $arcNode) {
        $arcNode = $xml.SelectSingleNode("/d:daml/d:ArcGIS", $ns)
    }

    if ($arcNode -and $arcNode.Attributes["defaultAssembly"]) {
        return $arcNode.Attributes["defaultAssembly"].Value
    }

    return "GeoMacroAddin.dll"
}

function Resolve-AddinId {
    param([string]$ConfigPath)

    if (-not (Test-Path $ConfigPath)) {
        return ""
    }

    [xml]$xml = Get-Content $ConfigPath -Encoding UTF8
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("d", "http://schemas.esri.com/DADF/Registry")

    $node = $xml.SelectSingleNode("/d:ArcGIS/d:AddInInfo", $ns)
    if (-not $node) {
        $node = $xml.SelectSingleNode("/d:daml/d:ArcGIS/d:AddInInfo", $ns)
    }

    if ($node -and $node.Attributes["id"]) {
        return $node.Attributes["id"].Value
    }

    return ""
}

function New-AddinPackage {
    param(
        [string]$ProjectDir,
        [string]$OutputDir,
        [string]$Configuration,
        [string]$AssemblyName
    )

    $configPath = Join-Path $ProjectDir "Config.daml"
    if (-not (Test-Path $configPath)) {
        throw "Config.daml not found: $configPath"
    }

    $tempRoot = Join-Path $ProjectDir "obj\$Configuration\net6.0-windows\temp_archive_custom"
    $installDir = Join-Path $tempRoot "Install"

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Get-ChildItem -Path $OutputDir -File | Where-Object {
        $_.Extension -notin @('.esriAddinX', '.zip')
    } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $installDir -Force
    }

    Get-ChildItem -Path $OutputDir -Directory | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $installDir -Recurse -Force
    }
    Copy-Item -Path $configPath -Destination (Join-Path $tempRoot "Config.daml") -Force

    $packageBaseName = [System.IO.Path]::GetFileNameWithoutExtension($AssemblyName)
    if ([string]::IsNullOrWhiteSpace($packageBaseName)) {
        $packageBaseName = "GeoMacroAddin"
    }

    $zipPath = Join-Path $OutputDir "$packageBaseName.zip"
    $addinPath = Join-Path $OutputDir "$packageBaseName.esriAddinX"

    if (Test-Path $zipPath) {
        Remove-Item -Path $zipPath -Force
    }
    if (Test-Path $addinPath) {
        Remove-Item -Path $addinPath -Force
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $tempRoot,
        $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false)
    Move-Item -Path $zipPath -Destination $addinPath -Force

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }

    return $addinPath
}

function Register-AddinPackage {
    param(
        [string]$ArcGISProDir,
        [string]$PackagePath
    )

    $registerExe = Join-Path $ArcGISProDir "bin\RegisterAddIn.exe"
    if (-not (Test-Path $registerExe)) {
        Write-Warning "RegisterAddIn.exe not found: $registerExe"
        return
    }

    & $registerExe "$PackagePath" /s
    if ($LASTEXITCODE -ne 0) {
        throw "RegisterAddIn.exe failed with exit code $LASTEXITCODE"
    }
}

function Deploy-AddinPackageToUserFolder {
    param(
        [string]$PackagePath,
        [string]$AddinId
    )

    $root = Join-Path $env:USERPROFILE "Documents\ArcGIS\AddIns\ArcGISPro"
    $folderName = if ([string]::IsNullOrWhiteSpace($AddinId)) { "GeoMacroAddin" } else { $AddinId }
    $targetDir = Join-Path $root $folderName

    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    $targetPath = Join-Path $targetDir ([System.IO.Path]::GetFileName($PackagePath))
    Copy-Item -Path $PackagePath -Destination $targetPath -Force
    return $targetPath
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$projectFullPath = Join-Path $repoRoot $ProjectPath
if (-not (Test-Path $projectFullPath)) {
    throw "Project file not found: $projectFullPath"
}

$arcgisDir = Resolve-ArcGISProInstallDir -OverridePath $ArcGISProInstallDir
Write-Host "Using ArcGIS Pro dir: $arcgisDir"
Write-Host "Building project: $projectFullPath"

Push-Location $repoRoot
try {
    dotnet build $projectFullPath -c $Configuration -p:ArcGISProInstallDir="$arcgisDir" -p:DisableArcGISPackaging=true /nologo

    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE"
    }

    $projectDir = Split-Path -Parent $projectFullPath
    $outputDir = Join-Path $projectDir "bin\$Configuration\net6.0-windows"
    if (Test-Path $outputDir) {
        $configPath = Join-Path $projectDir "Config.daml"
        $assemblyName = Resolve-DefaultAssemblyName -ConfigPath $configPath
        $addinId = Resolve-AddinId -ConfigPath $configPath
        $packagePath = New-AddinPackage -ProjectDir $projectDir -OutputDir $outputDir -Configuration $Configuration -AssemblyName $assemblyName
        Register-AddinPackage -ArcGISProDir $arcgisDir -PackagePath $packagePath
        $userPath = Deploy-AddinPackageToUserFolder -PackagePath $packagePath -AddinId $addinId
        Write-Host "Add-in package generated and registered: $packagePath"
        Write-Host "Add-in package copied to user AddIns folder: $userPath"
    }
} finally {
    Pop-Location
}
