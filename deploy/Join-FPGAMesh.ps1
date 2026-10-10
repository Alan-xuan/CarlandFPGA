<#
Join a public FPGA Mesh source repository and configure one local agent node.
Run from a teammate's Codex session. Human login and Feishu app approval remain
interactive; this script never embeds API keys in Git or the distribution ZIP.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('A', 'B', 'C')]
    [string]$Node,
    [string]$Repository = 'https://github.com/carolwjade/CarlandFPGA.git',
    [string]$Workspace = (Join-Path $HOME 'Documents\CarlandFPGA'),
    [string]$PythonExe = '',
    [string]$DeepSeekKeyFile = '',
    [string]$SharedSecretFile = '',
    [string]$GroupId = 'oc_e0de73230fd64dd2da3e52fc781dffb1',
    [string]$AstraAppId = '',
    [string]$AstraSecretFile = '',
    [string]$DeepSeekAppId = '',
    [string]$DeepSeekSecretFile = '',
    [string]$PeerA = '',
    [string]$PeerB = '',
    [string]$PeerC = '',
    [string]$BindHost = '',
    [switch]$RegisterApps = $true,
    [switch]$SkipTailscale,
    [switch]$SkipAutostart,
    [switch]$SkipStart,
    [switch]$SetUpFork = $true,
    [switch]$SkipLiveSmoke,
    [switch]$SkipToolInstall
)

$ErrorActionPreference = 'Stop'
if (-not $SkipToolInstall) {
    & (Join-Path $PSScriptRoot 'Install-Prerequisites.ps1')
}
$repoRoot = [System.IO.Path]::GetFullPath($Workspace)
$parent = Split-Path -Parent $repoRoot
New-Item -ItemType Directory -Path $parent -Force | Out-Null
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required. Install Git for Windows, then rerun this command.'
}
if (-not (Test-Path -LiteralPath $repoRoot)) {
    & git clone --origin upstream $Repository $repoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Git clone failed.' }
} else {
    $actual = (& git -C $repoRoot remote get-url upstream 2>$null)
    if ($LASTEXITCODE -ne 0) {
        $actual = (& git -C $repoRoot remote get-url origin 2>$null)
    }
    if ($LASTEXITCODE -ne 0 -or $actual.TrimEnd('/') -ne $Repository.TrimEnd('/')) {
        throw "Workspace is not the requested repository: $repoRoot"
    }
    $dirty = & git -C $repoRoot status --porcelain
    if (-not $dirty) {
        $remoteName = if ((& git -C $repoRoot remote) -contains 'upstream') { 'upstream' } else { 'origin' }
        & git -C $repoRoot pull --ff-only $remoteName main
        if ($LASTEXITCODE -ne 0) { throw 'Git fast-forward update failed.' }
    } else {
        Write-Warning 'Workspace has local edits; leaving them untouched and using the installed checkout.'
    }
}

$venvPython = Join-Path $repoRoot '.local\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $created = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $repoRoot '.local\venv')
        $created = ($LASTEXITCODE -eq 0)
    }
    if (-not $created) {
        $candidates = @()
        if ($PythonExe) { $candidates += $PythonExe }
        $installedPython = Get-Command python -ErrorAction SilentlyContinue
        if ($installedPython) { $candidates += $installedPython.Source }
        $runtimeRoot = Join-Path $HOME '.cache\codex-runtimes'
        if (Test-Path -LiteralPath $runtimeRoot) {
            $candidates += @(Get-ChildItem -Path (Join-Path $runtimeRoot '*\dependencies\python\python.exe') -File -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName)
        }
        foreach ($candidate in ($candidates | Select-Object -Unique)) {
            if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
            & $candidate -c 'import sys; assert sys.version_info >= (3,12)' 2>$null
            if ($LASTEXITCODE -ne 0) { continue }
            & $candidate -m venv (Join-Path $repoRoot '.local\venv')
            if ($LASTEXITCODE -eq 0) { $created = $true; break }
        }
    }
    if (-not $created -or -not (Test-Path -LiteralPath $venvPython)) {
        throw 'Python 3.12+ is required. Install it, then rerun this command.'
    }
}
& $venvPython -c 'import sys; assert sys.version_info >= (3,12)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
Push-Location -LiteralPath $repoRoot
try {
    & $venvPython -m pip install -e '.[feishu]'
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    $nodeRoot = Join-Path $repoRoot ('.local\deployment\node-' + $Node.ToLower())
    New-Item -ItemType Directory -Path $nodeRoot -Force | Out-Null
    $feishuRoot = Join-Path $nodeRoot 'feishu'
    if ($RegisterApps) {
        foreach ($role in @('astra', 'deepseek')) {
            $manifest = Join-Path $feishuRoot "$role.json"
            if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
                try {
                    & $venvPython deploy/register-feishu-apps.py --node $Node --role $role --output-dir $feishuRoot
                    $registered = ($LASTEXITCODE -eq 0)
                } catch {
                    $registered = $false
                }
                if (-not $registered) {
                    Write-Warning "Feishu $role registration needs account authorization or a retry. Other setup continues; rerun this script after completing it."
                }
            }
        }
    }
    $astraManifest = Join-Path $feishuRoot 'astra.json'
    $deepseekManifest = Join-Path $feishuRoot 'deepseek.json'
    if (-not $AstraAppId -and (Test-Path -LiteralPath $astraManifest)) {
        $saved = Get-Content -LiteralPath $astraManifest -Raw | ConvertFrom-Json
        $AstraAppId = $saved.app_id
        $AstraSecretFile = $saved.secret_file
    }
    if (-not $DeepSeekAppId -and (Test-Path -LiteralPath $deepseekManifest)) {
        $saved = Get-Content -LiteralPath $deepseekManifest -Raw | ConvertFrom-Json
        $DeepSeekAppId = $saved.app_id
        $DeepSeekSecretFile = $saved.secret_file
    }

    # A newly joined identity is not marked online until it has posted one
    # marked group message and read that exact message back as the same app.
    # The local receipt makes retries safe if the read fails after the send.
    if ($GroupId -and $AstraAppId -and $AstraSecretFile) {
        $astraState = Join-Path $feishuRoot 'astra-selftest.json'
        & $venvPython -m fpga_mesh.feishu_selftest --node $Node --role astra `
            --app-id $AstraAppId --secret-file $AstraSecretFile --group-id $GroupId `
            --state-file $astraState
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Astra Feishu send/read self-test is incomplete; Feishu remains disabled. Publish and add the bot to the group, then rerun.'
            $AstraAppId = ''
            $AstraSecretFile = ''
        }
    } elseif ($AstraAppId -or $AstraSecretFile) {
        Write-Warning 'Astra Feishu identity is incomplete; Feishu remains disabled.'
        $AstraAppId = ''
        $AstraSecretFile = ''
    }
    if ($GroupId -and $DeepSeekAppId -and $DeepSeekSecretFile) {
        $deepseekState = Join-Path $feishuRoot 'deepseek-selftest.json'
        & $venvPython -m fpga_mesh.feishu_selftest --node $Node --role deepseek `
            --app-id $DeepSeekAppId --secret-file $DeepSeekSecretFile --group-id $GroupId `
            --state-file $deepseekState
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'DeepSeek Feishu send/read self-test is incomplete; its group identity remains disabled. Publish and add the bot to the group, then rerun.'
            $DeepSeekAppId = ''
            $DeepSeekSecretFile = ''
        }
    } elseif ($DeepSeekAppId -or $DeepSeekSecretFile) {
        Write-Warning 'DeepSeek Feishu identity is incomplete; its group identity remains disabled.'
        $DeepSeekAppId = ''
        $DeepSeekSecretFile = ''
    }

    if (-not $SkipTailscale) {
        $tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
        if (-not $tailscale) {
            $candidate = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
            if (Test-Path -LiteralPath $candidate) { $tailscale = @{ Source = $candidate } }
        }
        if (-not $tailscale) {
            Write-Warning 'Tailscale is not installed; install it and log into the shared tailnet for direct B/C communication.'
        } elseif (-not $BindHost) {
            $tailIp = (& $tailscale.Source ip -4 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $tailIp -match '^100\.') { $BindHost = $tailIp }
        }
    }
    $configPath = Join-Path $nodeRoot ("node-$($Node.ToLower()).toml")
    $arguments = @('--node', $Node, '--output', $configPath, '--reuse-existing')
    if ($BindHost) { $arguments += @('--bind-host', $BindHost) }
    foreach ($entry in @(
        @('deepseek-key-file', $DeepSeekKeyFile),
        @('shared-secret-file', $SharedSecretFile),
        @('group-id', $GroupId),
        @('astra-app-id', $AstraAppId),
        @('astra-secret-file', $AstraSecretFile),
        @('deepseek-app-id', $DeepSeekAppId),
        @('deepseek-secret-file', $DeepSeekSecretFile),
        @('peer-a', $PeerA), @('peer-b', $PeerB), @('peer-c', $PeerC)
    )) {
        if ($entry[1]) { $arguments += @(('--' + $entry[0]), [string]$entry[1]) }
    }
    & $venvPython -m fpga_mesh.onboarding @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Node config generation failed.' }
    # A retry may omit paths already recorded in the ignored local config.
    if (-not $DeepSeekKeyFile) {
        $DeepSeekKeyFile = & $venvPython -c 'import sys; from fpga_mesh.runtime import NodeConfig; p=NodeConfig.load(sys.argv[1]).deepseek_key_file; print(str(p) if p else "")' $configPath
    }
    if (-not $SharedSecretFile) {
        $SharedSecretFile = & $venvPython -c 'import sys; from fpga_mesh.runtime import NodeConfig; p=NodeConfig.load(sys.argv[1]).peer_shared_secret_file; print(str(p) if p else "")' $configPath
    }
    & $venvPython -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Self-test failed; service was not started.' }

    if ($SetUpFork) {
        $gh = Get-Command gh -ErrorAction SilentlyContinue
        $ghReady = $false
        if ($gh) {
            & gh auth status *> $null
            $ghReady = ($LASTEXITCODE -eq 0)
        }
        if ($ghReady) {
            $canPush = & gh api repos/carolwjade/CarlandFPGA --jq '.permissions.push' 2>$null
            if ($LASTEXITCODE -eq 0 -and $canPush -eq 'true') {
                Write-Host 'Upstream collaborator write access verified; personal fork is optional.'
            } else {
                $login = & gh api user --jq '.login' 2>$null
                if ($LASTEXITCODE -eq 0 -and $login) {
                    $forkName = "$login/CarlandFPGA"
                    & gh repo view $forkName --json nameWithOwner *> $null
                    if ($LASTEXITCODE -ne 0) {
                        & gh repo fork carolwjade/CarlandFPGA --clone=false --remote=true
                    }
                    & gh repo view $forkName --json nameWithOwner *> $null
                    if ($LASTEXITCODE -eq 0) {
                        $forkUrl = "https://github.com/$forkName.git"
                        $remotes = @(& git -C $repoRoot remote)
                        if ($remotes -notcontains 'origin') {
                            & git -C $repoRoot remote add origin $forkUrl
                            if ($LASTEXITCODE -ne 0) { Write-Warning 'Fork exists, but origin remote setup failed.' }
                        } else {
                            $originUrl = & git -C $repoRoot remote get-url origin
                            if ($originUrl.TrimEnd('/') -ne $forkUrl.TrimEnd('/')) {
                                Write-Warning 'Origin already points elsewhere; preserving it. Verify fork remote before pushing.'
                            }
                        }
                    } else {
                        Write-Warning 'Fork setup failed; source checkout remains usable.'
                    }
                } else {
                    Write-Warning 'GitHub login exists but account identity could not be read; fork setup deferred.'
                }
            }
        } else {
            Write-Warning 'GitHub CLI login is needed to create your fork and submit pull requests.'
        }
    }
    $mainControlFile = Join-Path $nodeRoot (".local/node-{0}/main-control.json" -f $Node.ToLowerInvariant())
    & $venvPython -m fpga_mesh.install_routing --project-root $repoRoot --python $venvPython --control-file $mainControlFile
    if ($LASTEXITCODE -ne 0) { throw 'Project routing bridge installation failed.' }
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    $codexReady = $false
    if ($codex) {
        & codex login status *> $null
        $codexReady = ($LASTEXITCODE -eq 0)
    }
    if (-not $codexReady) { Write-Warning 'Log in to Codex with the local ChatGPT subscription.' }
    $keyReady = $DeepSeekKeyFile -and (Test-Path -LiteralPath $DeepSeekKeyFile -PathType Leaf)
    if (-not $keyReady) { Write-Warning 'Provide a local DeepSeek API key file before starting child agents.' }
    if (-not $SkipLiveSmoke -and $codexReady -and $keyReady) {
        $smokePath = Join-Path $nodeRoot 'parent-child-smoke.json'
        $revision = (& git -C $repoRoot rev-parse HEAD).Trim()
        $smokeCurrent = $false
        if (Test-Path -LiteralPath $smokePath -PathType Leaf) {
            try {
                $oldSmoke = Get-Content -LiteralPath $smokePath -Raw | ConvertFrom-Json
                $smokeCurrent = ($oldSmoke.revision -eq $revision -and
                    $oldSmoke.parent_accepted -eq $true -and
                    $oldSmoke.parent_text.Trim() -eq 'CHILD_OK' -and
                    ($oldSmoke.pool_efforts -join ',') -eq 'max')
            } catch { $smokeCurrent = $false }
        }
        if (-not $smokeCurrent) {
            try {
                $smokeLines = @(& $venvPython -m scripts.smoke_parent_child --node $Node --key-file $DeepSeekKeyFile)
                if ($LASTEXITCODE -ne 0) { throw 'The live parent-child command failed.' }
                $smoke = $smokeLines[-1] | ConvertFrom-Json
                $completed = @($smoke.child_jobs | Where-Object {
                    $_.status -eq 'completed' -and $_.result_text.Trim() -eq 'CHILD_OK'
                }).Count -gt 0
                if ($smoke.parent_accepted -ne $true -or
                    $smoke.parent_text.Trim() -ne 'CHILD_OK' -or
                    -not $smoke.parent_effort -or -not $completed -or
                    ($smoke.pool_efforts -join ',') -ne 'max') {
                    throw 'The parent-child result did not satisfy the live verification checks.'
                }
                [ordered]@{
                    revision = $revision
                    parent_accepted = $smoke.parent_accepted
                    parent_text = $smoke.parent_text
                    parent_effort = $smoke.parent_effort
                    child_jobs = $smoke.child_jobs
                    pool_efforts = $smoke.pool_efforts
                } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $smokePath -Encoding utf8
                Write-Host 'Live Astra-to-DeepSeek delegation verified and receipt saved locally.'
            } catch {
                Write-Warning "Live parent-child delegation is pending: $($_.Exception.Message)"
            }
        }
    }
    if (-not $SkipAutostart -and $codexReady -and $keyReady) {
        & pwsh -NoProfile -File deploy/register-autostart.ps1 -Node $Node -Config $configPath -Python $venvPython -StartNow:$(-not $SkipStart)
        if ($LASTEXITCODE -ne 0) { throw 'Scheduled task registration failed.' }
    } elseif (-not $SkipAutostart) {
        Write-Warning 'Autostart deferred until Codex login and the local DeepSeek key are ready.'
    }
    Write-Host "Workspace: $repoRoot"
    Write-Host "Local config: $configPath"
    Write-Host "Feishu enabled: $([bool]($GroupId -and $AstraAppId -and $AstraSecretFile))"
    $sharedFileReady = $SharedSecretFile -and (Test-Path -LiteralPath $SharedSecretFile -PathType Leaf) -and
        ((Get-Item -LiteralPath $SharedSecretFile).Length -gt 0)
    Write-Host "Shared mesh secret file present: $([bool]$sharedFileReady)"
    Write-Host 'The public repository can be cloned by anyone; write access requires a fork and pull request or an explicit collaborator grant.'
    $statusPath = Join-Path $nodeRoot 'setup-status.json'
    $stepsPath = Join-Path $nodeRoot 'NEXT_STEPS.md'
    & $venvPython -m fpga_mesh.setup_gates --workspace $repoRoot --node $Node `
        --output-json $statusPath --output-markdown $stepsPath
    if ($LASTEXITCODE -ne 0) { throw 'Setup status generation failed.' }
    Write-Host "Credential-free setup report: $statusPath"
    Write-Host "Human-action and retry guide: $stepsPath"
} finally {
    Pop-Location
}
