<# Install this standalone skill into one local Codex profile. #>
param([string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }))

$ErrorActionPreference = 'Stop'
$source = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$skillsRoot = [System.IO.Path]::GetFullPath((Join-Path $CodexHome 'skills'))
$target = [System.IO.Path]::GetFullPath((Join-Path $skillsRoot 'pynq-z2-single-node'))
if (-not $target.StartsWith($skillsRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Skill target resolved outside the Codex skills directory.'
}
if ($source -eq $target) {
    Write-Host "Skill is already installed at $target"
    exit 0
}
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
$files = @(Get-ChildItem -LiteralPath $source -File -Recurse | Where-Object {
    $_.Extension -ne '.pyc' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]'
})
if (-not ($files | Where-Object { $_.FullName -eq (Join-Path $source 'SKILL.md') })) {
    throw 'Source skill is incomplete: SKILL.md is missing.'
}
$same = (Test-Path -LiteralPath $target -PathType Container)
if ($same) {
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($source.Length + 1)
        $installed = Join-Path $target $relative
        if (-not (Test-Path -LiteralPath $installed -PathType Leaf) -or
            (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash) {
            $same = $false
            break
        }
    }
    if ($same -and @(Get-ChildItem -LiteralPath $target -File -Recurse).Count -ne $files.Count) {
        $same = $false
    }
}
if ($same) {
    Write-Host "Skill already matches package at $target"
    exit 0
}
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 8)
$staging = Join-Path $skillsRoot (".pynq-z2-single-node.new-$suffix")
$backup = Join-Path $skillsRoot ("pynq-z2-single-node.backup-$suffix")
New-Item -ItemType Directory -Path $staging -Force | Out-Null
foreach ($file in $files) {
    $relative = $file.FullName.Substring($source.Length + 1)
    $copy = Join-Path $staging $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $copy) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $copy -Force
    if (-not (Test-Path -LiteralPath $copy -PathType Leaf) -or
        (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash) {
        throw "Skill staging verification failed: $relative"
    }
}
try {
    if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $backup }
    Move-Item -LiteralPath $staging -Destination $target
} catch {
    if (-not (Test-Path -LiteralPath $target) -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    throw
}
Write-Host "Installed PYNQ-Z2 single-node skill: $target"
if (Test-Path -LiteralPath $backup) { Write-Host "Previous version backup: $backup" }
