using ArcGIS.Desktop.Framework.Contracts;

namespace GeoMacroAddin.Commands;

internal sealed class ToggleCaptureButton : Button
{
    protected override void OnClick()
    {
        GeoMacroAddinModule.Current.ToggleCapture();
    }
}
