# GeoMacro Add-in Build and Run

## Prerequisites

- ArcGIS Pro installed locally.
- .NET SDK 6 installed.
- PowerShell execution policy allows local scripts.

## Build

From workspace root:

```powershell
./scripts/dev/build-addin.ps1
```

Optional explicit ArcGIS Pro directory:

```powershell
./scripts/dev/build-addin.ps1 -ArcGISProInstallDir "D:\ArcGIS Pro 3.0"
```

Expected result:

- Build succeeds.
- Script packages output into `.esriAddinX` under `addins/GeoMacroAddin/bin/Debug/net6.0-windows`.
- Package is silently registered by ArcGIS Pro `RegisterAddIn.exe`.

## Run ArcGIS Pro

```powershell
./scripts/dev/run-arcgis.ps1 -BuildFirst
```

## Commit 1 functional check

1. Open ArcGIS Pro and run 5 geoprocessing tools.
2. In GeoMacro tab, open Event Log panel.
3. Verify log entries include execute id, tool, start/finish info.
4. Verify JSONL output in:
   - `%USERPROFILE%\\Documents\\GeoMacro\\runtime\\events`
   - or custom `GEOMACRO_EVENT_DIR` directory.

## Validation scope

This step validates:

- Add-in compiles.
- Add-in packages and auto-registers.
- Event subscription and JSON persistence run end-to-end when tools are executed.

This step does not fully validate:

- Complex geoprocessing history merge logic (Commit 2).
- Full script generation pipeline correctness (Commit 3/4).

## Commit 2 merge runner

After running tools in ArcGIS Pro, use this helper to merge live JSONL events with ArcGIS history XML:

```powershell
./scripts/dev/run-commit2-merge.ps1
```

Optional examples:

```powershell
# Force a specific live file
./scripts/dev/run-commit2-merge.ps1 -ScriptArgs @("--live-jsonl", "C:\Users\<you>\Documents\GeoMacro\runtime\events\gp-events-20260421.jsonl")

# Scan a larger history window
./scripts/dev/run-commit2-merge.ps1 -ScriptArgs @("--lookback-hours", "72", "--history-files", "100")

# Export only enriched (named) events
./scripts/dev/run-commit2-merge.ps1 -ScriptArgs @("--only-named-events")
```

Expected output:

- Merged session JSON saved under `runtime/merged/commit2-merged-<timestamp>.json`.
- Summary counts for live events, history items, and merged incremental events.
