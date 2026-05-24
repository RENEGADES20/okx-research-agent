param(
    [int]$Port = 8080,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $BundledPython) {
    $Python = $BundledPython
} else {
    $Python = "python"
}

Set-Location $ProjectRoot
& $Python (Join-Path $ProjectRoot "serve.py") --host $HostName --port $Port
