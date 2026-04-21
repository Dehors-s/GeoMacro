using System;

namespace GeoMacroAddin.Models;

internal sealed class GpEventRecord
{
    public string ExecuteId { get; init; } = string.Empty;
    public string ToolPath { get; init; } = string.Empty;
    public string ToolName { get; init; } = string.Empty;
    public bool IsStarting { get; init; }
    public bool? IsSuccess { get; init; }
    public string ResultSummary { get; init; } = string.Empty;
    public DateTime TimestampUtc { get; init; } = DateTime.UtcNow;
}
