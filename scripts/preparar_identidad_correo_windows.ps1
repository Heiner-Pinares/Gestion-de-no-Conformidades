param(
    [string]$ServiceAccount = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPath = Join-Path $ProjectRoot ".env"
$SecretsDirectory = Join-Path $ProjectRoot "secrets"
$KnownHostsPath = Join-Path $SecretsDirectory "correo_known_hosts"

function Assert-Administrator {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Abra PowerShell como administrador para preparar la identidad SSH."
    }
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

Assert-Administrator
if (-not (Test-Path $Python -PathType Leaf)) {
    throw "No existe .venv. Ejecute primero scripts\instalar_windows_oracle.ps1."
}
if (-not (Test-Path $EnvPath -PathType Leaf)) {
    throw "Falta .env. Configure el portal antes de preparar el correo."
}
try {
    $Account = [Security.Principal.NTAccount]::new($ServiceAccount)
    $null = $Account.Translate([Security.Principal.SecurityIdentifier])
}
catch {
    throw "La cuenta $ServiceAccount no existe o no puede resolverse en este servidor."
}

New-Item -ItemType Directory -Force -Path $SecretsDirectory | Out-Null
Set-EnvValue -Name "CORREO_SSH_KNOWN_HOSTS" -Value ($KnownHostsPath.Replace("\", "/"))

Set-Location $ProjectRoot
& $Python "manage.py" "preparar_identidad_correo" "--archivo" $KnownHostsPath
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo preparar la identidad SSH del servidor de correo."
}

& icacls $KnownHostsPath /inheritance:r /grant:r "${ServiceAccount}:(R)" "SYSTEM:(F)" "BUILTIN\Administrators:(F)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "La identidad se obtuvo, pero no se pudieron restringir sus permisos."
}

if (-not (Test-Path $KnownHostsPath -PathType Leaf)) {
    throw "La preparacion termino sin crear $KnownHostsPath."
}
$KnownHostsItem = Get-Item $KnownHostsPath -ErrorAction Stop
if ($KnownHostsItem.Length -le 0) {
    throw "El archivo $KnownHostsPath quedo vacio."
}
try {
    $Reader = [IO.File]::OpenRead($KnownHostsPath)
    $Reader.Dispose()
}
catch {
    throw "La cuenta actual no puede leer $KnownHostsPath. $($_.Exception.Message)"
}

$ConfiguredLine = Select-String -Path $EnvPath -Pattern '^CORREO_SSH_KNOWN_HOSTS=' | Select-Object -Last 1
if (-not $ConfiguredLine -or $ConfiguredLine.Line -ne "CORREO_SSH_KNOWN_HOSTS=$($KnownHostsPath.Replace('\', '/'))") {
    throw "No se pudo confirmar CORREO_SSH_KNOWN_HOSTS en .env."
}

Write-Host "Identidad SSH lista. El portal solo necesita leer $KnownHostsPath."
Write-Host "Archivo verificado: $($KnownHostsItem.Length) bytes."
