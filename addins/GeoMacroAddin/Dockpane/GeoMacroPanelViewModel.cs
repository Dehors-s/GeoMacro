using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Input;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;
using GeoMacroAddin.Models;
using GeoMacroAddin.Services;

namespace GeoMacroAddin.Dockpane;

internal sealed class GeoMacroPanelViewModel : DockPane
{
    private const string DockpaneId = "GeoMacroAddin_GeoMacroPanel";

    private readonly PythonRunner _runner;
    private string _scriptPreview = "";
    private string _statusText = "Ready.";
    private bool _isGenerating;

    public GeoMacroPanelViewModel()
    {
        _runner = new PythonRunner(
            pythonPath: @"D:\Conda_Data\envs\geomacro_env\python.exe",
            projectRoot: @"D:\Work space\GEO\GeoMacro"
        );

        RefreshHistoryCommand = new RelayCommand(_ => RefreshHistory());
        SelectAllCommand = new RelayCommand(_ => SetAllSelected(true));
        DeselectAllCommand = new RelayCommand(_ => SetAllSelected(false));
        GenerateScriptCommand = new RelayCommand(_ => _ = GenerateScriptAsync(), _ => !IsGenerating);
        SaveScriptCommand = new RelayCommand(_ => SaveScript(), _ => !string.IsNullOrWhiteSpace(ScriptPreview));
    }

    public ObservableCollection<HistoryEventItem> Events { get; } = new();

    public string ScriptPreview
    {
        get => _scriptPreview;
        set { _scriptPreview = value; OnPropertyChanged(); }
    }

    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; OnPropertyChanged(); }
    }

    public bool IsGenerating
    {
        get => _isGenerating;
        set
        {
            _isGenerating = value;
            OnPropertyChanged();
            CommandManager.InvalidateRequerySuggested();
        }
    }

    public int SelectedCount => Events.Count(e => e.IsSelected);

    public ICommand RefreshHistoryCommand { get; }
    public ICommand SelectAllCommand { get; }
    public ICommand DeselectAllCommand { get; }
    public ICommand GenerateScriptCommand { get; }
    public ICommand SaveScriptCommand { get; }

    public static void Show()
    {
        var pane = FrameworkApplication.DockPaneManager.Find(DockpaneId);
        pane?.Activate();
    }

    public void RefreshHistory()
    {
        StatusText = "Loading history...";

        var mergedDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "GeoMacro", "runtime", "merged"
        );
        if (!Directory.Exists(mergedDir))
            mergedDir = @"D:\Work space\GEO\GeoMacro\runtime\merged";

        Events.Clear();

        if (!Directory.Exists(mergedDir))
        {
            StatusText = "No history found. Capture events first.";
            return;
        }

        var jsonFiles = Directory.GetFiles(mergedDir, "*.json")
            .OrderByDescending(f => File.GetLastWriteTime(f))
            .Take(5);

        foreach (var file in jsonFiles)
        {
            try
            {
                var json = File.ReadAllText(file, System.Text.Encoding.UTF8);
                var arr = JsonSerializer.Deserialize<System.Text.Json.JsonElement[]>(json);
                if (arr == null) continue;

                foreach (var el in arr)
                {
                    var item = new HistoryEventItem
                    {
                        EventId = el.TryGetProperty("event_id", out var id) ? id.GetString() ?? "" : "",
                        ToolName = el.TryGetProperty("tool_name", out var tn) ? tn.GetString() ?? "" : "",
                        ToolPath = el.TryGetProperty("tool_path", out var tp) ? tp.GetString() ?? "" : "",
                        Source = el.TryGetProperty("source", out var src) ? src.GetString() ?? "" : "",
                        IsSuccess = el.TryGetProperty("is_success", out var succ) && succ.GetBoolean(),
                        Timestamp = el.TryGetProperty("timestamp", out var ts) ? ts.GetString() ?? "" : "",
                        IsSelected = true,
                    };
                    Events.Add(item);
                }
            }
            catch
            {
                // Skip unparseable files
            }
        }

        StatusText = $"Loaded {Events.Count} events. {SelectedCount} selected.";
        OnPropertyChanged(nameof(SelectedCount));
    }

    private void SetAllSelected(bool selected)
    {
        foreach (var evt in Events)
            evt.IsSelected = selected;
        OnPropertyChanged(nameof(SelectedCount));
        StatusText = $"{Events.Count} events, {SelectedCount} selected.";
    }

    private async System.Threading.Tasks.Task GenerateScriptAsync()
    {
        IsGenerating = true;
        StatusText = "Generating script via GeoMacro pipeline...";

        var result = await _runner.RunGeoMacroAsync(lookbackHours: 720);

        if (result.Success && result.ScriptPath != null)
        {
            ScriptPreview = File.ReadAllText(result.ScriptPath, System.Text.Encoding.UTF8);
            StatusText = $"Generated: {result.ScriptPath}";
            if (!string.IsNullOrWhiteSpace(result.StdErr))
                StatusText += $" (stderr: {result.StdErr.Length} chars)";
        }
        else
        {
            ScriptPreview = "// Generation failed.\n" +
                           $"// Exit code: {result.ExitCode}\n" +
                           $"// stderr:\n{result.StdErr}";
            StatusText = "Generation failed.";
        }

        IsGenerating = false;
    }

    private void SaveScript()
    {
        if (string.IsNullOrWhiteSpace(ScriptPreview)) return;

        var dlg = new Microsoft.Win32.SaveFileDialog
        {
            Filter = "Python files (*.py)|*.py|All files (*.*)|*.*",
            FileName = "geomacro_pipeline.py",
            DefaultExt = ".py",
        };

        if (dlg.ShowDialog() == true)
        {
            File.WriteAllText(dlg.FileName, ScriptPreview, System.Text.Encoding.UTF8);
            StatusText = $"Saved to {dlg.FileName}";
        }
    }
}
