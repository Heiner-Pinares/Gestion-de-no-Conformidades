param(
    [string]$BindHost = "0.0.0.0",
    [ValidateRange(1, 65535)]
    [int]$Port = 8001,
    [ValidateRange(4, 128)]
    [int]$Threads = 8,
    [string]$RuntimeRoot = "$env:ProgramData\PortalNC"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPath = Join-Path $ProjectRoot ".env"
$LogDirectory = Join-Path $RuntimeRoot "logs"

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$LogPath = Join-Path $LogDirectory ("portal-{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-PortalLog {
    param([string]$Message)
    $Line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    [IO.File]::AppendAllText($LogPath, "$Line`r`n", [Text.UTF8Encoding]::new($false))
}

try {
    if (-not (Test-Path $Python -PathType Leaf)) {
        throw "No existe $Python. Ejecute primero scripts\instalar_windows_oracle.ps1."
    }
    if (-not (Test-Path $EnvPath -PathType Leaf)) {
        throw "Falta $EnvPath. Configure el portal antes de publicarlo."
    }

    # run.py lee estos valores del entorno del proceso. No contienen secretos.
    $env:PORTAL_BIND_HOST = $BindHost
    $env:PORTAL_PORT = [string]$Port
    $env:PORTAL_THREADS = [string]$Threads
    $env:PYTHONUNBUFFERED = "1"

    Set-Location $ProjectRoot
    Write-PortalLog "Inicio solicitado en ${BindHost}:${Port} con ${Threads} hilos."
    # Escribir cada linea abriendo y cerrando el archivo permite consultar el
    # log mientras Waitress sigue activo. La redireccion *>> mantiene el archivo
    # bloqueado durante toda la vida del proceso en Windows PowerShell 5.1.
    & $Python -u "run.py" "start" 2>&1 | ForEach-Object {
        $OutputLine = [string]$_
        [IO.File]::AppendAllText($LogPath, "$OutputLine`r`n", [Text.UTF8Encoding]::new($false))
    }
    $ExitCode = $LASTEXITCODE
    Write-PortalLog "El proceso termino con codigo $ExitCode."
    exit $ExitCode
}
catch {
    Write-PortalLog ("ERROR: " + $_.Exception.Message)
    throw
}
