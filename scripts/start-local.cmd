@echo off
setlocal
cd /d "%~dp0.."
set "invoicePython=%CD%\.venv\Scripts\python.exe"
if exist "%invoicePython%" goto run
set "invoicePython=C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe"
if exist "%invoicePython%" goto run
set "invoicePython=python"
:run
if not defined PORT set "PORT=8000"
set "PYTHON_BIN=%invoicePython%"
if exist "%CD%\.tools\tesseract\tesseract.exe" set "PATH=%CD%\.tools\tesseract;%PATH%"
if not defined PUBLIC_URL set "PUBLIC_URL=http://localhost:%PORT%"
if not exist "node_modules\express" (
  echo Installing web dependencies...
  call npm.cmd ci --no-fund
  if errorlevel 1 exit /b 1
)
node web/server.mjs
exit /b %errorlevel%
