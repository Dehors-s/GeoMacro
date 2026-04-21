# GeoMacroAddin Commit 1 PoC

This folder contains the first MVP add-in implementation slice:

- Subscribe to `GPExecuteToolEvent`
- Convert event args to a stable JSON record DTO
- Append records to daily JSONL files
- Provide a minimal dockpane for runtime logs

## Delivered files

- `Module1.cs`: module bootstrap, start capture on initialize.
- `Events/GpEventSubscriber.cs`: subscribe/unsubscribe logic and mapping from args to DTO.
- `Models/GpEventRecord.cs`: event DTO.
- `Services/EventJsonWriter.cs`: JSONL persistence.
- `Services/EventLogService.cs`: in-memory log relay for UI.
- `Dockpane/EventLogDockpaneViewModel.cs`: minimal panel state.
- `Dockpane/EventLogDockpane.xaml`: minimal panel view.
- `Commands/ShowEventLogDockpaneButton.cs`: open log panel.
- `Commands/ToggleCaptureButton.cs`: start/stop capture.
- `Config.daml`: module, buttons and dockpane registration.

## Runtime output

By default, event JSONL files are written to:

`%USERPROFILE%\\Documents\\GeoMacro\\runtime\\events`

You can override the output directory with environment variable:

`GEOMACRO_EVENT_DIR`

## Event JSON example

```json
{"ExecuteId":"...","ToolPath":"analysis/Buffer","ToolName":"Buffer","IsStarting":false,"IsSuccess":true,"ResultSummary":"ErrorCode=0; ReturnValue=...","TimestampUtc":"2026-04-20T08:01:22.1234567Z"}
```

## Validation checklist

1. Start ArcGIS Pro with this add-in loaded.
2. Open GeoMacro tab and click "Open Event Log".
3. Run 5 geoprocessing tools (for example Buffer and Clip).
4. Confirm panel shows new entries for each event.
5. Confirm JSONL file contains execute id, tool path, is_starting, and result summary.

## Notes

- Event callback may execute on a non-UI thread; dockpane updates are marshaled to dispatcher.
- Current PoC appends JSON lines without rotation policies beyond daily file partition.
- This is intentionally minimal and designed for Commit 1 acceptance.
