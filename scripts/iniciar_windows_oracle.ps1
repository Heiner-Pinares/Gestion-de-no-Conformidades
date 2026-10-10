$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "No existe .venv. Cree el entorno e instale requirements-oracle.txt."
}
if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    throw "Falta .env. Copie .env.oracle.example y complete los valores reales."
}
Set-Location $ProjectRoot
& $Python "run.py" "start"
if ($LASTEXITCODE -ne 0) { throw "El Portal NC no pudo iniciar." }
