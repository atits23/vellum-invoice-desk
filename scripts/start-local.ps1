param([int]$Port = 8000, [string]$DataDirectory = '')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$localPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) {
    $invoicePython = $localPython
} else {
    $bundledPython = 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $invoicePython = $bundledPython } else { $invoicePython = 'python' }
}
$env:PORT = [string]$Port
if ($DataDirectory) { $env:DATA_DIR = $DataDirectory }
$env:PYTHON_BIN = $invoicePython
if (Test-Path '.tools\tesseract\tesseract.exe') { $env:PATH = "$(Get-Location)\.tools\tesseract;$env:PATH" }
if (-not $env:PUBLIC_URL) { $env:PUBLIC_URL = "http://localhost:$Port" }
if (-not (Test-Path 'node_modules\express')) { & npm.cmd ci --no-fund }
& node web/server.mjs
