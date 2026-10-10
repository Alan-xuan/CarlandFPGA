param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("A", "B", "C")]
    [string]$Node,
    [Parameter(Mandatory = $true)]
    [string]$Config,
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$configPath = [System.IO.Path]::GetFullPath($Config)
$pythonPath = [System.IO.Path]::GetFullPath($Python)
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Node config not found: $configPath"
}
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python executable not found: $pythonPath"
}
$taskName = "FPGA-Mesh-Node-$Node"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -notlike "FPGA Mesh $Node controller*") {
    throw "Scheduled task exists and is not owned by FPGA Mesh: $taskName"
}
$nodeDir = Split-Path -Parent $configPath
$readyFile = Join-Path $nodeDir "ready.json"
$logFile = Join-Path $nodeDir "service.log"
$arguments = '-m fpga_mesh.supervisor --config "{0}" --ready-file "{1}" --log-file "{2}"' -f `
    $configPath, $readyFile, $logFile
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments `
    -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew
if ($existing) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Push-Location $repo
    try {
        & $pythonPath -m fpga_mesh.service --wait-stopped --config $configPath --timeout 20
        if ($LASTEXITCODE -ne 0) { throw 'Previous FPGA service has not finished stopping; preserving single-instance protection.' }
    } finally { Pop-Location }
    Set-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings | Out-Null
} else {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "FPGA Mesh $Node controller; event-driven idle" | Out-Null
}
if ($StartNow) {
    Start-ScheduledTask -TaskName $taskName
}
Write-Host "Registered $taskName"
Write-Host "Ready file: $readyFile"
