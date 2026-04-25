using System;
using System.Windows.Input;
using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;

namespace GeoMacroAddin.Commands;

internal sealed class ShowGeoMacroPanelButton : Button
{
    protected override void OnClick()
    {
        Dockpane.GeoMacroPanelViewModel.Show();
    }
}
