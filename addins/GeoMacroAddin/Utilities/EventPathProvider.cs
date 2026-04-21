using System;
using System.IO;

namespace GeoMacroAddin.Utilities;

internal static class EventPathProvider
{
    public static string ResolveEventDirectory()
    {
        var configuredPath = Environment.GetEnvironmentVariable("GEOMACRO_EVENT_DIR");
        if (!string.IsNullOrWhiteSpace(configuredPath))
        {
            return configuredPath;
        }

        var docsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        return Path.Combine(docsPath, "GeoMacro", "runtime", "events");
    }
}
