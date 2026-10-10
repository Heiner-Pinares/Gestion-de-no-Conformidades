param(
    [string]$ClientDir = "C:\oracle\instantclient_19"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python -PathType Leaf)) {
    throw "No existe .venv. Ejecute primero scripts\instalar_windows_oracle.ps1."
}

$OciDll = Join-Path $ClientDir "oci.dll"
if (-not (Test-Path $OciDll -PathType Leaf)) {
    throw "No se encontró $OciDll. Extraiga Oracle Instant Client Basic x64 en $ClientDir."
}

$Architecture = & $Python -c "import struct; print(struct.calcsize('P') * 8)"
if ($Architecture -ne "64") {
    throw "Python debe ser de 64 bits para Oracle Instant Client x64."
}

$env:PORTAL_ORACLE_CLIENT_LIB_DIR = $ClientDir
& $Python -c "import os, oracledb; oracledb.init_oracle_client(lib_dir=os.environ['PORTAL_ORACLE_CLIENT_LIB_DIR']); print('Oracle Client:', oracledb.clientversion()); print('Modo Thick:', not oracledb.is_thin_mode())"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo cargar Oracle Instant Client. Revise su arquitectura y Microsoft Visual C++ Redistributable."
}

$EnvPath = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvPath -PathType Leaf)) {
    Copy-Item ".env.oracle.example" $EnvPath
}

function Set-EnvValue {
    param([string]$Name, [string]$Value)
    $Text = [IO.File]::ReadAllText($EnvPath)
    $Pattern = "(?m)^" + [Regex]::Escape($Name) + "=.*$"
    $Line = "$Name=$Value"
    if ([Regex]::IsMatch($Text, $Pattern)) {
        $Text = [Regex]::Replace($Text, $Pattern, $Line)
    }
    else {
        if ($Text.Length -gt 0 -and -not $Text.EndsWith("`n")) { $Text += "`r`n" }
        $Text += "$Line`r`n"
    }
    [IO.File]::WriteAllText($EnvPath, $Text, [Text.UTF8Encoding]::new($false))
}

$PortablePath = $ClientDir.Replace("\", "/")
Set-EnvValue -Name "ORACLE_THICK_MODE" -Value "True"
Set-EnvValue -Name "ORACLE_CLIENT_LIB_DIR" -Value $PortablePath

Write-Host "Modo Oracle Thick habilitado en .env con $PortablePath."
Write-Host "Ejecute: .\.venv\Scripts\python.exe run.py check"
