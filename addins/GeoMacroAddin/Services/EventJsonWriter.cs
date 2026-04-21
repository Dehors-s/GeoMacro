using System;
using System.IO;
using System.Text;
using System.Text.Json;
using GeoMacroAddin.Models;

namespace GeoMacroAddin.Services;

internal sealed class EventJsonWriter
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = false
    };

    private readonly object _syncLock = new();
    private readonly string _eventDirectory;

    public EventJsonWriter(string eventDirectory)
    {
        _eventDirectory = eventDirectory;
        Directory.CreateDirectory(_eventDirectory);
    }

    public string Append(GpEventRecord record)
    {
        var filePath = Path.Combine(_eventDirectory, $"gp-events-{DateTime.UtcNow:yyyyMMdd}.jsonl");
        var line = JsonSerializer.Serialize(record, JsonOptions) + Environment.NewLine;

        lock (_syncLock)
        {
            File.AppendAllText(filePath, line, Encoding.UTF8);
        }

        return filePath;
    }
}
