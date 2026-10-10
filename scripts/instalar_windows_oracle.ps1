param(
    [string]$PythonLauncher = "py"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual con Python 3.12..."
    & $PythonLauncher -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear .venv con Python 3.12." }
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($Version -ne "3.12") {
    throw "El entorno usa Python $Version. Este despliegue fue validado con Python 3.12."
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falló la actualización de pip." }
& $Python -m pip install --requirement requirements-oracle.txt --require-hashes
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias Oracle." }

New-Item -ItemType Directory -Force -Path secrets | Out-Null
if (-not (Test-Path ".env")) {
    Copy-Item ".env.oracle.example" ".env"
    Write-Host "Se creó .env desde el ejemplo. Complete host, SERVICE_NAME, usuario y dominio."
}

Write-Host "Instalación de Python terminada. Ejecute scripts\configurar_secretos_windows.ps1 y luego python run.py check."
