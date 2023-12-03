using System.Text.Json;
using Microsoft.Diagnostics.Tracing.Etlx;
using Microsoft.Diagnostics.Tracing.Parsers.Clr;
using Microsoft.Diagnostics.Tracing.Stacks;

var fileToConvert = args[0];

var etlxFilePath = TraceLog.CreateFromEventPipeDataFile(fileToConvert);
using (var eventLog = new TraceLog(etlxFilePath))
{
    var stats = CalculateMemoryStats(eventLog);
    var jsonString = JsonSerializer.Serialize(stats, new JsonSerializerOptions
    {
        WriteIndented = true
    });

    Console.WriteLine(jsonString);
}

if (File.Exists(etlxFilePath))
{
    File.Delete(etlxFilePath);
}

return;

static MemoryStats CalculateMemoryStats(TraceLog eventLog)
{
    var stackSource = new MutableTraceEventStackSource(eventLog)
    {
        OnlyManagedCodeStacks = true // EventPipe currently only has managed code stacks.
    };

    var result = new MemoryStats();

    foreach (var @event in stackSource.TraceLog.Events)
    {
        if (@event is GCAllocationTickTraceData gcTickEvent)
            result.AllocationAmount += gcTickEvent.AllocationAmount64;
    }

    return result;
}

internal record struct MemoryStats(long AllocationAmount);