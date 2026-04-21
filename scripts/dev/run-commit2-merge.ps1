param(
    [string[]]$ScriptArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$scriptPath = Join-Path $PSScriptRoot "run-commit2-merge.py"

if (-not (Test-Path $scriptPath)) {
    throw "Python entry script not found: $scriptPath"
}

Push-Location $repoRoot
try {
    python $scriptPath @ScriptArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
