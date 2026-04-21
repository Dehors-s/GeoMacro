using System;
using System.Collections.ObjectModel;
using System.Windows;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;
using GeoMacroAddin.Services;

namespace GeoMacroAddin.Dockpane;

internal class EventLogDockpaneViewModel : DockPane
{
    private const string DockpaneId = "GeoMacroAddin_EventLogDockpane";
    private readonly ObservableCollection<string> _entries = new();

    protected EventLogDockpaneViewModel()
    {
        foreach (var entry in EventLogService.Instance.GetRecentEntries())
        {
            AddEntry(entry);
        }

        EventLogService.Instance.EntryAdded += OnEntryAdded;
    }

    public ObservableCollection<string> Entries => _entries;

    public static void Show()
    {
        var pane = FrameworkApplication.DockPaneManager.Find(DockpaneId);
        pane?.Activate();
    }

    private void OnEntryAdded(string entry)
    {
        if (string.IsNullOrWhiteSpace(entry))
        {
            return;
        }

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher != null && !dispatcher.CheckAccess())
        {
            dispatcher.Invoke(() => AddEntry(entry));
            return;
        }

        AddEntry(entry);
    }

    private void AddEntry(string entry)
    {
        // Keep a small ring buffer to avoid unbounded memory growth.
        while (_entries.Count >= 200)
        {
            _entries.RemoveAt(0);
        }

        _entries.Add(entry);
        NotifyPropertyChanged(nameof(Entries));
    }
}
