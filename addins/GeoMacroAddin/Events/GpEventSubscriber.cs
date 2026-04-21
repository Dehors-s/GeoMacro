using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using ArcGIS.Desktop.Framework.Threading.Tasks;
using GeoMacroAddin.Models;
using GeoMacroAddin.Services;

namespace GeoMacroAddin.Events;

internal sealed class GpEventSubscriber : IDisposable
{
    private static readonly string[] CoreAssemblyNameCandidates =
    {
        "ArcGIS.Desktop.Core",
        "ArcGIS.Desktop.Core, Version=13.0.0.0, Culture=neutral, PublicKeyToken=8fc3cc631e44ad86"
    };

    private static readonly string[] EventTypeCandidates =
    {
        "ArcGIS.Desktop.Core.Events.GPExecuteToolEvent",
        "ArcGIS.Desktop.Core.Events.GPToolExecuteEvent",
        "ArcGIS.Desktop.Internal.Core.Events.GPToolExecuteEvent"
    };

    private readonly EventJsonWriter _writer;
    private readonly EventLogService _logService;
    private readonly object _stateLock = new();
    private object? _subscriptionToken;
    private MethodInfo? _unsubscribeMethod;
    private object? _unsubscribeArgument;

    public GpEventSubscriber(EventJsonWriter writer, EventLogService logService)
    {
        _writer = writer;
        _logService = logService;
    }

    public bool IsCapturing
    {
        get
        {
            lock (_stateLock)
            {
                return _subscriptionToken != null;
            }
        }
    }

    public void Start()
    {
        RunOnMctOrCurrent(() =>
        {
            lock (_stateLock)
            {
                if (_subscriptionToken != null)
                {
                    return;
                }
            }

            if (TrySubscribe())
            {
                return;
            }

            _logService.Add("No compatible GP execute event type was found for this ArcGIS Pro version.");
        }, "Start capture");
    }

    public void Stop()
    {
        RunOnMctOrCurrent(StopCore, "Stop capture");
    }

    private void StopCore()
    {
        object? token;
        MethodInfo? unsubscribeMethod;
        object? unsubscribeArgument;

        lock (_stateLock)
        {
            token = _subscriptionToken;
            unsubscribeMethod = _unsubscribeMethod;
            unsubscribeArgument = _unsubscribeArgument;

            _subscriptionToken = null;
            _unsubscribeMethod = null;
            _unsubscribeArgument = null;
        }

        if (token == null)
        {
            return;
        }

        try
        {
            if (unsubscribeMethod != null && unsubscribeArgument != null)
            {
                unsubscribeMethod.Invoke(null, new[] { unsubscribeArgument });
                _logService.Add("GP execute event subscription stopped.");
            }
            else
            {
                _logService.Add("Capture state reset (no compatible unsubscribe overload).");
            }
        }
        catch (Exception ex)
        {
            _logService.Add($"Failed to stop GP execute event subscription: {FlattenException(ex)}");
        }
    }

    public void Dispose()
    {
        Stop();
    }

    private bool TrySubscribe()
    {
        foreach (var typeName in EventTypeCandidates)
        {
            var eventType = ResolveType(typeName);
            if (eventType == null)
            {
                _logService.Add($"Event type not found: {typeName}");
                continue;
            }

            var subscribeMethod = eventType
                .GetMethods(BindingFlags.Public | BindingFlags.Static)
                .FirstOrDefault(method =>
                    method.Name == "Subscribe" &&
                    method.GetParameters().Length >= 1 &&
                    typeof(Delegate).IsAssignableFrom(method.GetParameters()[0].ParameterType));

            if (subscribeMethod == null)
            {
                _logService.Add($"Subscribe method not found on: {typeName}");
                continue;
            }

            var delegateType = subscribeMethod.GetParameters()[0].ParameterType;
            var handlerDelegate = BuildHandlerDelegate(delegateType);
            if (handlerDelegate == null)
            {
                _logService.Add($"Unable to build handler delegate for: {typeName}");
                continue;
            }

            object? token;
            try
            {
                token = subscribeMethod.Invoke(null, BuildSubscribeArgs(subscribeMethod, handlerDelegate));
            }
            catch (Exception ex)
            {
                _logService.Add($"Subscribe failed on {typeName}: {FlattenException(ex)}");
                continue;
            }

            if (token == null)
            {
                _logService.Add($"Subscribe returned null token on: {typeName}");
                continue;
            }

            var unsubscribeCandidates = eventType
                .GetMethods(BindingFlags.Public | BindingFlags.Static)
                .Where(method => method.Name == "Unsubscribe" && method.GetParameters().Length == 1)
                .ToArray();

            MethodInfo? unsubscribeMethod = null;
            object? unsubscribeArgument = null;

            unsubscribeMethod = unsubscribeCandidates.FirstOrDefault(method =>
                method.GetParameters()[0].ParameterType.IsInstanceOfType(token));
            if (unsubscribeMethod != null)
            {
                unsubscribeArgument = token;
            }
            else
            {
                unsubscribeMethod = unsubscribeCandidates.FirstOrDefault(method =>
                    method.GetParameters()[0].ParameterType.IsInstanceOfType(handlerDelegate));
                if (unsubscribeMethod != null)
                {
                    unsubscribeArgument = handlerDelegate;
                }
            }

            lock (_stateLock)
            {
                _subscriptionToken = token;
                _unsubscribeMethod = unsubscribeMethod;
                _unsubscribeArgument = unsubscribeArgument;
            }

            if (unsubscribeMethod == null)
            {
                _logService.Add($"Subscribed to {typeName}, but no compatible Unsubscribe overload was found.");
            }
            else
            {
                _logService.Add($"Subscribed to {typeName}.");
            }

            if (typeName == "ArcGIS.Desktop.Internal.Core.Events.GPToolExecuteEvent")
            {
                _logService.Add("ArcGIS Pro 3.0 payload has no tool path/id in this event; records will show generic tool name.");
            }

            return true;
        }

        return false;
    }

    private static Type? ResolveType(string fullTypeName)
    {
        var direct = Type.GetType($"{fullTypeName}, ArcGIS.Desktop.Core", throwOnError: false);
        if (direct != null)
        {
            return direct;
        }

        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            var candidate = assembly.GetType(fullTypeName, throwOnError: false);
            if (candidate != null)
            {
                return candidate;
            }
        }

        foreach (var assemblyName in CoreAssemblyNameCandidates)
        {
            try
            {
                var coreAssembly = Assembly.Load(assemblyName);
                var candidate = coreAssembly.GetType(fullTypeName, throwOnError: false);
                if (candidate != null)
                {
                    return candidate;
                }
            }
            catch
            {
                // Keep probing other assembly names.
            }
        }

        return null;
    }

    private static object?[] BuildSubscribeArgs(MethodInfo subscribeMethod, Delegate handlerDelegate)
    {
        var parameters = subscribeMethod.GetParameters();
        var args = new object?[parameters.Length];

        if (parameters.Length > 0)
        {
            args[0] = handlerDelegate;
        }

        for (var i = 1; i < parameters.Length; i++)
        {
            var parameter = parameters[i];
            if (parameter.ParameterType == typeof(bool))
            {
                var keepAlive = string.Equals(parameter.Name, "keepSubscriberAlive", StringComparison.OrdinalIgnoreCase);
                args[i] = keepAlive;
            }
            else if (parameter.HasDefaultValue)
            {
                args[i] = parameter.DefaultValue;
            }
            else if (parameter.ParameterType.IsValueType)
            {
                args[i] = Activator.CreateInstance(parameter.ParameterType);
            }
            else
            {
                args[i] = null;
            }
        }

        return args;
    }

    private static string FlattenException(Exception ex)
    {
        if (ex is TargetInvocationException tie && tie.InnerException != null)
        {
            return $"{tie.InnerException.GetType().Name}: {tie.InnerException.Message}";
        }

        return $"{ex.GetType().Name}: {ex.Message}";
    }

    private void RunOnMctOrCurrent(Action action, string operationName)
    {
        if (QueuedTask.OnWorker)
        {
            action();
            return;
        }

        try
        {
            _ = QueuedTask.Run(() =>
            {
                try
                {
                    action();
                }
                catch (Exception ex)
                {
                    _logService.Add($"{operationName} failed on MCT: {FlattenException(ex)}");
                }
            });
        }
        catch (Exception ex)
        {
            _logService.Add($"{operationName} could not queue to MCT, fallback to current thread: {FlattenException(ex)}");
            action();
        }
    }

    private Delegate? BuildHandlerDelegate(Type delegateType)
    {
        var invokeMethod = delegateType.GetMethod("Invoke");
        var parameters = invokeMethod?.GetParameters();
        if (parameters == null || parameters.Length != 1)
        {
            return null;
        }

        var argType = parameters[0].ParameterType;
        var genericHandler = GetType().GetMethod(
            nameof(OnGpEventCore),
            BindingFlags.Instance | BindingFlags.NonPublic);
        if (genericHandler == null)
        {
            return null;
        }

        var closedHandler = genericHandler.MakeGenericMethod(argType);
        try
        {
            return Delegate.CreateDelegate(delegateType, this, closedHandler);
        }
        catch
        {
            return null;
        }
    }

    private void OnGpEventCore<TArgs>(TArgs args)
    {
        OnGpExecuteToolEvent(args!);
    }

    private void OnGpExecuteToolEvent(object args)
    {
        var record = BuildRecord(args);
        var filePath = _writer.Append(record);
        var displayTime = record.TimestampUtc.ToLocalTime();

        var successText = record.IsSuccess.HasValue ? record.IsSuccess.Value.ToString() : "unknown";
        _logService.Add(
            $"{displayTime:HH:mm:ss} [{record.ExecuteId}] {record.ToolName} " +
            $"start={record.IsStarting} success={successText} -> {filePath}");
    }

    private static GpEventRecord BuildRecord(object args)
    {
        var toolPath = TryGetPropertyText(args, "Path");
        if (string.IsNullOrWhiteSpace(toolPath))
        {
            toolPath = TryGetPropertyText(args, "ToolPath");
        }

        var gpResult = TryGetPropertyValue(args, "GPResult");
        if (gpResult == null)
        {
            gpResult = TryGetPropertyValue(args, "Result");
        }

        var executeId = TryGetPropertyText(args, "ID");
        if (string.IsNullOrWhiteSpace(executeId))
        {
            executeId = TryGetPropertyText(args, "ExecuteID");
        }

        var timestamp = DateTime.UtcNow;
        if (string.IsNullOrWhiteSpace(executeId))
        {
            executeId = $"evt-{timestamp:HHmmssfff}";
        }

        var isBeginning = TryGetBoolean(args, "IsBeginning");
        var isStarting = TryGetBoolean(args, "IsStarting") ?? isBeginning ?? false;
        var inEditSession = TryGetBoolean(args, "InEditSession");
        var isSuccess = TryGetBoolean(args, "IsSucceeded");

        var isFailed = TryGetBoolean(gpResult, "IsFailed");
        if (!isSuccess.HasValue)
        {
            isSuccess = isFailed.HasValue ? !isFailed.Value : null;
        }

        return new GpEventRecord
        {
            ExecuteId = executeId,
            ToolPath = toolPath,
            ToolName = ExtractToolName(toolPath),
            IsStarting = isStarting,
            IsSuccess = isSuccess,
            ResultSummary = BuildResultSummary(gpResult, inEditSession, isBeginning),
            TimestampUtc = timestamp
        };
    }

    private static string ExtractToolName(string toolPath)
    {
        if (string.IsNullOrWhiteSpace(toolPath))
        {
            return "GPExecuteEvent";
        }

        var normalized = toolPath.Replace('\\', '/');
        var parts = normalized.Split('/');
        return parts.LastOrDefault() ?? normalized;
    }

    private static string BuildResultSummary(object? gpResult, bool? inEditSession, bool? isBeginning)
    {
        var parts = new List<string>();

        if (isBeginning.HasValue)
        {
            parts.Add($"IsBeginning={isBeginning.Value}");
        }

        if (inEditSession.HasValue)
        {
            parts.Add($"InEditSession={inEditSession.Value}");
        }

        if (gpResult == null)
        {
            return string.Join("; ", parts);
        }

        var errorCode = TryGetPropertyText(gpResult, "ErrorCode");
        var returnValue = TryGetPropertyText(gpResult, "ReturnValue");
        if (!string.IsNullOrWhiteSpace(errorCode))
        {
            parts.Add($"ErrorCode={errorCode}");
        }

        if (!string.IsNullOrWhiteSpace(returnValue))
        {
            parts.Add($"ReturnValue={returnValue}");
        }

        return string.Join("; ", parts);
    }

    private static bool? TryGetBoolean(object? target, string propertyName)
    {
        if (target == null)
        {
            return null;
        }

        var prop = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
        if (prop == null)
        {
            return null;
        }

        var value = prop.GetValue(target);
        return value is bool boolean ? boolean : null;
    }

    private static string TryGetPropertyText(object target, string propertyName)
    {
        var prop = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
        if (prop == null)
        {
            return string.Empty;
        }

        var value = prop.GetValue(target);
        return value?.ToString() ?? string.Empty;
    }

    private static object? TryGetPropertyValue(object target, string propertyName)
    {
        var prop = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
        if (prop == null)
        {
            return null;
        }

        return prop.GetValue(target);
    }
}
