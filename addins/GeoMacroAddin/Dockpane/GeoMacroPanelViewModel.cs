using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text.Json;
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
    private string _sourceFilter = "arcgis_pro";
    private ObservableCollection<HistoryEventItem> _allEvents = new();

    public GeoMacroPanelViewModel()
    {
        _runner = new PythonRunner(
            pythonPath: @"D:\Conda_Data\envs\geomacro_env\python.exe",
            projectRoot: @"D:\Work space\GEO\GeoMacro"
        );

        RefreshHistoryCommand = new RelayCommand(() => RefreshHistory());
        SelectAllCommand = new RelayCommand(() => SetAllSelected(true));
        DeselectAllCommand = new RelayCommand(() => SetAllSelected(false));
        FilterProCommand = new RelayCommand(() => SetSourceFilter("arcgis_pro"));
        FilterDesktopCommand = new RelayCommand(() => SetSourceFilter("arcgis_desktop"));
        FilterAllCommand = new RelayCommand(() => SetSourceFilter("all"));
        GenerateScriptCommand = new RelayCommand(() => { _ = GenerateScriptAsync(); }, () => !IsGenerating);
        RunScriptCommand = new RelayCommand(() => { _ = RunScriptAsync(); }, () => !IsGenerating);
        SaveScriptCommand = new RelayCommand(() => SaveScript(), () => !string.IsNullOrWhiteSpace(ScriptPreview));
    }

    public ObservableCollection<HistoryEventItem> Events { get; } = new();

    public string ScriptPreview
    {
        get => _scriptPreview;
        set { _scriptPreview = value; NotifyPropertyChanged(); }
    }

    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; NotifyPropertyChanged(); }
    }

    public bool IsGenerating
    {
        get => _isGenerating;
        set
        {
            _isGenerating = value;
            NotifyPropertyChanged();
            CommandManager.InvalidateRequerySuggested();
        }
    }

    public string SourceFilter
    {
        get => _sourceFilter;
        set { _sourceFilter = value; NotifyPropertyChanged(); ApplyFilter(); }
    }

    public int SelectedCount => Events.Count(e => e.IsSelected);

    public ICommand RefreshHistoryCommand { get; }
    public ICommand SelectAllCommand { get; }
    public ICommand DeselectAllCommand { get; }
    public ICommand FilterProCommand { get; }
    public ICommand FilterDesktopCommand { get; }
    public ICommand FilterAllCommand { get; }
    public ICommand GenerateScriptCommand { get; }
    public ICommand RunScriptCommand { get; }
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

        _allEvents.Clear();

        if (!Directory.Exists(mergedDir))
        {
            StatusText = "No history found. Capture events first.";
            ApplyFilter();
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
                var arr = JsonSerializer.Deserialize<JsonElement[]>(json);
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
                    _allEvents.Add(item);
                }
            }
            catch
            {
            }
        }

        ApplyFilter();
    }

    private void SetSourceFilter(string filter)
    {
        SourceFilter = filter;
    }

    private void ApplyFilter()
    {
        Events.Clear();

        var filtered = _sourceFilter switch
        {
            "arcgis_pro" => _allEvents.Where(e => e.Source == "arcgis_pro" || e.Source == ""),
            "arcgis_desktop" => _allEvents.Where(e => e.Source == "arcgis_desktop"),
            _ => _allEvents,
        };

        foreach (var item in filtered)
            Events.Add(item);

        NotifyPropertyChanged(nameof(SelectedCount));
        StatusText = $"[{_sourceFilter}] {Events.Count} events, {SelectedCount} selected.";
    }

    private void SetAllSelected(bool selected)
    {
        foreach (var evt in Events)
            evt.IsSelected = selected;
        NotifyPropertyChanged(nameof(SelectedCount));
        StatusText = $"[{_sourceFilter}] {Events.Count} events, {SelectedCount} selected.";
    }

    private async System.Threading.Tasks.Task GenerateScriptAsync()
    {
        IsGenerating = true;
        StatusText = "Generating script via GeoMacro pipeline...";

        var result = await _runner.RunGeoMacroAsync(lookbackHours: 720);

        if (result.Success && result.ScriptPath != null)
        {
            ScriptPreview = File.ReadAllText(result.ScriptPath, System.Text.Encoding.UTF8);
            _lastScriptPath = result.ScriptPath;
            StatusText = $"Generated: {result.ScriptPath}";
            if (!string.IsNullOrWhiteSpace(result.StdErr))
                StatusText += $" (stderr: {result.StdErr.Length} chars)";
        }
        else
        {
            ScriptPreview = "// Generation failed.\n" +
                           $"// Exit code: {result.ExitCode}\n" +
                           $"// stderr:\n{result.StdErr}";
            _lastScriptPath = null;
            StatusText = "Generation failed.";
        }

        IsGenerating = false;
    }

    private string? _lastScriptPath;

    private async System.Threading.Tasks.Task RunScriptAsync()
    {
        if (string.IsNullOrWhiteSpace(_lastScriptPath) || !File.Exists(_lastScriptPath))
        {
            StatusText = "No generated script found. Click Generate first.";
            return;
        }

        IsGenerating = true;
        StatusText = "Running script...";

        var psi = new System.Diagnostics.ProcessStartInfo
        {
            FileName = @"D:\Conda_Data\envs\geomacro_env\python.exe",
            Arguments = $"\"{_lastScriptPath}\" --input \"{_runner.ProjectRoot}\" --output \"{_runner.ProjectRoot}\\output\\run\"",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(_lastScriptPath),
        };

        psi.EnvironmentVariables["PYTHONPATH"] = Path.Combine(_runner.ProjectRoot, "src");

        try
        {
            using var proc = new System.Diagnostics.Process { StartInfo = psi };
            proc.Start();
            var stdout = await proc.StandardOutput.ReadToEndAsync();
            var stderr = await proc.StandardError.ReadToEndAsync();
            await proc.WaitForExitAsync();

            var output = $"Exit code: {proc.ExitCode}\n{stdout}";
            if (!string.IsNullOrWhiteSpace(stderr))
                output += $"\n--- stderr ---\n{stderr}";

            ScriptPreview = output;
            StatusText = proc.ExitCode == 0
                ? $"Script executed successfully (exit 0). Saved to output/run/"
                : $"Script failed (exit {proc.ExitCode}). See preview for details.";
        }
        catch (Exception ex)
        {
            ScriptPreview = $"Failed to launch script:\n{ex}";
            StatusText = "Failed to launch script.";
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
