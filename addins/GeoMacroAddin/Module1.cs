using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;
using GeoMacroAddin.Events;
using GeoMacroAddin.Services;
using GeoMacroAddin.Utilities;

namespace GeoMacroAddin;

internal sealed class GeoMacroAddinModule : Module
{
    private static GeoMacroAddinModule? _instance;
    private GpEventSubscriber? _subscriber;

    public static GeoMacroAddinModule Current =>
        _instance ??= (GeoMacroAddinModule)FrameworkApplication.FindModule("GeoMacroAddin_Module");

    protected override bool Initialize()
    {
        var eventDir = EventPathProvider.ResolveEventDirectory();
        var writer = new EventJsonWriter(eventDir);

        _subscriber = new GpEventSubscriber(writer, EventLogService.Instance);
        _subscriber.Start();

        EventLogService.Instance.Add($"GeoMacro initialized. Event output: {eventDir}");
        return true;
    }

    protected override bool CanUnload()
    {
        _subscriber?.Dispose();
        return true;
    }

    public bool IsCapturing => _subscriber?.IsCapturing ?? false;

    public void ToggleCapture()
    {
        if (_subscriber == null)
        {
            EventLogService.Instance.Add("Capture service is not ready yet.");
            return;
        }

        if (_subscriber.IsCapturing)
        {
            _subscriber.Stop();
        }
        else
        {
            _subscriber.Start();
        }
    }
}
