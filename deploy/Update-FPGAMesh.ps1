<# Update an existing node without rerunning onboarding or replacing secrets. #>
param(
    [Parameter(Mandatory = $true)][ValidateSet('A', 'B', 'C')][string]$Node,
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$Config = '',
    [string]$Python = '',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repo = [System.IO.Path]::GetFullPath($Workspace)
$packagePath = [System.IO.Path]::GetFullPath($Package)
$packageRoot = Split-Path -Parent $PSScriptRoot
$updater = Join-Path $packageRoot 'fpga_mesh/update.py'
if (-not $Config) { $Config = Join-Path $repo ('.local/deployment/node-{0}/node-{0}.toml' -f $Node.ToLowerInvariant()) }
if (-not $Python) { $Python = Join-Path $repo '.local/venv/Scripts/python.exe' }
$configPath = [System.IO.Path]::GetFullPath($Config)
$pythonPath = [System.IO.Path]::GetFullPath($Python)
foreach ($path in @($packagePath, $updater, $configPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required existing file not found: $path" }
}
$updateArgs = @($updater, '--package', $packagePath, '--workspace', $repo, '--config', $configPath, '--node', $Node)
$preflight = @(& $pythonPath @updateArgs)
if ($LASTEXITCODE -ne 0) { throw ('Update preflight blocked; existing files and service preserved. ' + ($preflight -join "`n")) }
$plan = ($preflight -join "`n") | ConvertFrom-Json
Write-Output ($preflight -join "`n")
if ($CheckOnly) { return }
$taskName = "FPGA-Mesh-Node-$Node"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -notlike "FPGA Mesh $Node controller*") {
    throw "Scheduled task is not owned by this node: $taskName"
}
if ($existing) {
    Stop-ScheduledTask -TaskName $taskName
    Push-Location $packageRoot
    try {
        & $pythonPath -m fpga_mesh.service --wait-stopped --config $configPath --timeout 20
        if ($LASTEXITCODE -ne 0) { throw 'Previous service has not stopped; update not applied.' }
    } finally { Pop-Location }
}
$control = [string]$plan.control_file
try {
    & $pythonPath @updateArgs --apply
    if ($LASTEXITCODE -ne 0) { throw 'Source update failed; completed source writes were rolled back. Inspect the local backup receipt.' }
    Push-Location $repo
    try {
        & $pythonPath -m fpga_mesh.install_routing --project-root $repo --python $pythonPath --control-file $control
        if ($LASTEXITCODE -ne 0) { throw 'Source updated; project routing installation needs review before restarting.' }
        & (Join-Path $repo 'deploy/register-autostart.ps1') -Node $Node -Config $configPath -Python $pythonPath -StartNow
        $health = $null
        $deadline = (Get-Date).AddSeconds(60)
        do {
            $healthLines = @(& $pythonPath -m fpga_mesh.project_cli --control-file $control health 2>$null)
            if ($LASTEXITCODE -eq 0) {
                $health = ($healthLines -join "`n") | ConvertFrom-Json
                if ($health.started -and ((-not $health.feishu_enabled) -or $health.feishu_connected)) { break }
            }
            Start-Sleep -Seconds 1
        } while ((Get-Date) -lt $deadline)
        if (-not $health -or -not $health.started -or ($health.feishu_enabled -and -not $health.feishu_connected)) {
            throw 'Source updated; resident health/Feishu not ready. Inspect existing service.log; do not repeat onboarding.'
        }
        & $pythonPath -m fpga_mesh.project_cli --control-file $control models_refresh
        if ($LASTEXITCODE -ne 0) { throw 'Resident started; official model refresh failed. Preserve credentials and inspect the exact provider/catalog error.' }
        [ordered]@{
            revision = $plan.revision; node = $Node; sourceUpdated = $true
            residentStarted = $health.started; feishuConnected = $health.feishu_connected
            mainIdentity = $health.identities.main; childIdentity = $health.identities.deepseek
            nextStep = 'Open a newly loaded Codex project conversation to use the updated roles and project MCP.'
        } | ConvertTo-Json
    } finally { Pop-Location }
} catch {
    # Do not replay failed task work or rerun registration/onboarding blindly.
    throw
}
