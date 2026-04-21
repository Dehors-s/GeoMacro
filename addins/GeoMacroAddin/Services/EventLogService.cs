using System;
using System.Collections.Generic;

namespace GeoMacroAddin.Services;

internal sealed class EventLogService
{
    private const int MaxEntries = 500;
    private static readonly Lazy<EventLogService> LazyInstance =
        new(() => new EventLogService());
    private readonly object _syncLock = new();
    private readonly List<string> _entries = new();

    public static EventLogService Instance => LazyInstance.Value;

    private EventLogService()
    {
    }

    public event Action<string>? EntryAdded;

    public void Add(string entry)
    {
        lock (_syncLock)
        {
            _entries.Add(entry);
            if (_entries.Count > MaxEntries)
            {
                _entries.RemoveRange(0, _entries.Count - MaxEntries);
            }
        }

        EntryAdded?.Invoke(entry);
    }

    public IReadOnlyList<string> GetRecentEntries()
    {
        lock (_syncLock)
        {
            return _entries.ToArray();
        }
    }
}
