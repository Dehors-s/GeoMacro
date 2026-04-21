using ArcGIS.Desktop.Framework.Contracts;
using GeoMacroAddin.Dockpane;

namespace GeoMacroAddin.Commands;

internal sealed class ShowEventLogDockpaneButton : Button
{
    protected override void OnClick()
    {
        EventLogDockpaneViewModel.Show();
    }
}
