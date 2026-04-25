using System;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace GeoMacroAddin.Models;

internal sealed class HistoryEventItem : INotifyPropertyChanged
{
    private bool _isSelected;

    public string EventId { get; init; } = string.Empty;
    public string ToolName { get; init; } = string.Empty;
    public string ToolPath { get; init; } = string.Empty;
    public string Source { get; init; } = string.Empty;
    public bool IsSuccess { get; init; }
    public string Timestamp { get; init; } = string.Empty;
    public string ToolCall { get; init; } = string.Empty;

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected == value) return;
            _isSelected = value;
            OnPropertyChanged();
        }
    }

    public string DisplayName => string.IsNullOrWhiteSpace(ToolName)
        ? "UnknownTool"
        : ToolName;

    public string Badge => Source switch
    {
        "arcgis_pro" => "Pro",
        "arcgis_desktop" => "D10.8",
        _ => "?"
    };

    public string SuccessIcon => IsSuccess ? "✓" : "✗";

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}
