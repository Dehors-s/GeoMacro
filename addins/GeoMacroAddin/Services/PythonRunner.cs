using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

namespace GeoMacroAddin.Services;

internal sealed class PythonRunner
{
    private readonly string _pythonPath;
    private readonly string _projectRoot;

    public PythonRunner(string pythonPath, string projectRoot)
    {
        _pythonPath = pythonPath;
        _projectRoot = projectRoot;
    }

    public async Task<PythonResult> RunGeoMacroAsync(int lookbackHours = 24, bool includeFailed = false)
    {
        var sb = new StringBuilder();
        var errors = new StringBuilder();

        var psi = new ProcessStartInfo
        {
            FileName = _pythonPath,
            Arguments = $"-m geomacro --lookback {lookbackHours} --output-dir \"{_projectRoot}\\output\" --quiet",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = _projectRoot,
        };

        if (includeFailed)
            psi.Arguments += " --include-failed";

        psi.EnvironmentVariables["PYTHONPATH"] = Path.Combine(_projectRoot, "src");

        try
        {
            using var process = new Process { StartInfo = psi };
            process.Start();

            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();

            await Task.WhenAll(stdoutTask, stderrTask);
            await process.WaitForExitAsync();

            sb.Append(stdoutTask.Result);
            errors.Append(stderrTask.Result);

            var scriptPath = Path.Combine(_projectRoot, "output", "generated_script.py");
            var reportPath = Path.Combine(_projectRoot, "output", "validation_report.txt");

            return new PythonResult
            {
                ExitCode = process.ExitCode,
                StdOut = sb.ToString(),
                StdErr = errors.ToString(),
                ScriptPath = File.Exists(scriptPath) ? scriptPath : null,
                ReportPath = File.Exists(reportPath) ? reportPath : null,
            };
        }
        catch (Exception ex)
        {
            errors.AppendLine(ex.ToString());
            return new PythonResult
            {
                ExitCode = -1,
                StdOut = sb.ToString(),
                StdErr = errors.ToString(),
            };
        }
    }
}

internal sealed class PythonResult
{
    public int ExitCode { get; init; }
    public string StdOut { get; init; } = string.Empty;
    public string StdErr { get; init; } = string.Empty;
    public string? ScriptPath { get; init; }
    public string? ReportPath { get; init; }
    public bool Success => ExitCode == 0;
}
