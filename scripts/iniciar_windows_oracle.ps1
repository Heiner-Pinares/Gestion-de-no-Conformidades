$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Waitress = Join-Path $ProjectRoot ".venv\Scripts\waitress-serve.exe"

if (-not (Test-Path $Python)) {
    throw "No existe .venv. Cree el entorno e instale requirements-oracle.txt."
}
if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    throw "Falta .env. Copie .env.oracle.example y complete los valores reales."
}
if (-not (Test-Path $Waitress)) {
    throw "Falta Waitress. Ejecute: .venv\Scripts\pip install -r requirements-oracle.txt"
}

Set-Location $ProjectRoot

# Estas operaciones no crean ni modifican objetos de base de datos.
& $Python "scripts\verificar_oracle_dml.py"
if ($LASTEXITCODE -ne 0) { throw "Falló la verificación Oracle DML." }

& $Python "manage.py" "check" "--deploy"
if ($LASTEXITCODE -ne 0) { throw "Falló la validación de Django." }

& $Python "manage.py" "collectstatic" "--noinput"
if ($LASTEXITCODE -ne 0) { throw "Falló collectstatic." }

& $Waitress "--listen=0.0.0.0:8000" "config.wsgi:application"
