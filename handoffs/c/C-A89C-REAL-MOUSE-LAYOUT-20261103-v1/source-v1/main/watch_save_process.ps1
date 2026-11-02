param([Parameter(Mandatory=$true)][uint32]$ViewerProcessId)
$ErrorActionPreference = 'Stop'
$c56EventPath = Join-Path $PSScriptRoot 'ui/save-process-events.jsonl'
$c56StopPath = Join-Path $PSScriptRoot 'ui/stop-process-watch.flag'
$c56SourceStart = 'C56SaveStart'
$c56SourceStop = 'C56SaveStop'
$c56Started = [DateTime]::UtcNow
function Write-C56Record($Record) {
    [System.IO.File]::AppendAllText($c56EventPath, (($Record | ConvertTo-Json -Depth 5 -Compress) + "`n"), [System.Text.UTF8Encoding]::new($false))
}
try {
    Register-CimIndicationEvent -Query "SELECT * FROM Win32_ProcessStartTrace WHERE ParentProcessID = $ViewerProcessId" -SourceIdentifier $c56SourceStart | Out-Null
    Register-CimIndicationEvent -Query "SELECT * FROM Win32_ProcessStopTrace WHERE ParentProcessID = $ViewerProcessId" -SourceIdentifier $c56SourceStop | Out-Null
    Write-C56Record @{event='observer_ready';observed_utc=[DateTime]::UtcNow.ToString('o');viewer_pid=$ViewerProcessId;mechanism='CIM process lifecycle events, no model polling';max_seconds=1200}
    Write-Output 'C56_SAVE_PROCESS_OBSERVER_READY'
    while (([DateTime]::UtcNow - $c56Started).TotalSeconds -lt 1200 -and -not (Test-Path -LiteralPath $c56StopPath)) {
        $c56Event = Wait-Event -Timeout 1
        if ($null -eq $c56Event) { continue }
        if ($c56Event.SourceIdentifier -in @($c56SourceStart,$c56SourceStop)) {
            $c56ProcessEvent = $c56Event.SourceEventArgs.NewEvent
            $c56Row = @{event=$c56Event.SourceIdentifier;observed_utc=[DateTime]::UtcNow.ToString('o');process_id=$c56ProcessEvent.ProcessID;parent_process_id=$c56ProcessEvent.ParentProcessID;process_name=$c56ProcessEvent.ProcessName;event_time_created=$c56ProcessEvent.TIME_CREATED}
            if ($c56Event.SourceIdentifier -eq $c56SourceStop) { $c56Row.exit_status=$c56ProcessEvent.ExitStatus }
            Write-C56Record $c56Row
        }
        Remove-Event -EventIdentifier $c56Event.EventIdentifier
    }
}
finally {
    Unregister-Event -SourceIdentifier $c56SourceStart -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $c56SourceStop -ErrorAction SilentlyContinue
    Write-C56Record @{event='observer_closed';observed_utc=[DateTime]::UtcNow.ToString('o');stop_flag=(Test-Path -LiteralPath $c56StopPath)}
}
