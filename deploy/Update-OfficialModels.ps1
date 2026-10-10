param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExe) { $PythonExe = Join-Path $repoRoot '.local\venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Run Join-FPGAMesh.ps1 before opening the model manager.' }
Push-Location $repoRoot
try {
    & $PythonExe -m fpga_mesh.models_ui
    if ($LASTEXITCODE -ne 0) { throw 'The resident node must be running to open the official model manager.' }
} finally { Pop-Location }
