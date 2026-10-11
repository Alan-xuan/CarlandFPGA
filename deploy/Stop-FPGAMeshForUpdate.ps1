<# Called while the updater holds all existing node admission ledger locks. #>
param(
    [Parameter(Mandatory = $true)][ValidateSet('A', 'B', 'C')][string]$Node,
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Python
)
$ErrorActionPreference = 'Stop'
$taskName = "FPGA-Mesh-Node-$Node"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -notlike "FPGA Mesh $Node controller*") {
    throw "Scheduled task is not owned by this node: $taskName"
}
if ($existing) { Stop-ScheduledTask -TaskName $taskName }
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & $Python -m fpga_mesh.service --wait-stopped --config $Config --timeout 20
    if ($LASTEXITCODE -ne 0) { throw 'Previous service has not stopped; source update must not proceed.' }
} finally { Pop-Location }
