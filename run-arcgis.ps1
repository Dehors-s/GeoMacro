$scriptPath = Join-Path $PSScriptRoot "scripts\dev\run-arcgis.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "Target script not found: $scriptPath"
}

& $scriptPath @args
exit $LASTEXITCODE
