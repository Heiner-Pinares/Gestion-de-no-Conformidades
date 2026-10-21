param(
    [string]$ServiceAccount = "$env:USERDOMAIN\$env:USERNAME",
    [string]$PublicUrl = "http://172.19.194.219:8001",
    [string]$TaskName = "PortalNC",
    [ValidateRange(1, 65535)]
    [int]$Port = 8001,
    [ValidateRange(4, 128)]
    [int]$Threads = 8,
    [string[]]$AllowedRemoteAddress = @("LocalSubnet"),
    [switch]$AllowInternalHttp,
    [switch]$BehindHttpsProxy
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPath = Join-Path $ProjectRoot ".env"
$Runner = Join-Path $PSScriptRoot "ejecutar_portal_windows.ps1"
$SecretsDirectory = Join-Path $ProjectRoot "secrets"
$WorkDirectory = Join-Path $ProjectRoot "work"
$RuntimeRoot = Join-Path $env:ProgramData "PortalNC"
$StaticRoot = Join-Path $RuntimeRoot "staticfiles"
$LogDirectory = Join-Path $RuntimeRoot "logs"
$FirewallRule = "Portal NC - acceso interno"

function Assert-Administrator {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Abra PowerShell como administrador para publicar el portal."
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

function Test-TcpPort {
    param([string]$HostName, [int]$TargetPort)
    $Client = [Net.Sockets.TcpClient]::new()
    try {
        $Result = $Client.BeginConnect($HostName, $TargetPort, $null, $null)
        if (-not $Result.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $Client.EndConnect($Result)
        return $true
    }
    catch { return $false }
    finally { $Client.Dispose() }
}

Assert-Administrator

try {
    $Account = [Security.Principal.NTAccount]::new($ServiceAccount)
    $null = $Account.Translate([Security.Principal.SecurityIdentifier])
}
catch {
    throw "La cuenta $ServiceAccount no existe o no puede resolverse en este servidor."
}

if (-not (Test-Path $Python -PathType Leaf)) {
    throw "No existe .venv. Ejecute primero scripts\instalar_windows_oracle.ps1."
}
if (-not (Test-Path $EnvPath -PathType Leaf)) {
    throw "Falta .env. Configure Oracle y los secretos antes de publicar."
}
if (-not (Test-Path $Runner -PathType Leaf)) {
    throw "Falta el ejecutor $Runner. Actualice el repositorio completo."
}
if (-not (Test-Path $SecretsDirectory -PathType Container)) {
    throw "Falta la carpeta secrets. Ejecute scripts\configurar_secretos_windows.ps1 antes de publicar."
}

try {
    $Uri = [Uri]$PublicUrl
}
catch {
    throw "PublicUrl no es una URL valida. Use http://host:puerto o https://dominio."
}
if ($Uri.Scheme -notin @("http", "https") -or [string]::IsNullOrWhiteSpace($Uri.Host)) {
    throw "PublicUrl debe comenzar con http:// o https:// y contener un host."
}
if ($Uri.AbsolutePath -ne "/") {
    throw "PublicUrl no debe contener una ruta. Use solamente el origen del portal."
}

$Https = $Uri.Scheme -eq "https"
if ($Https -and -not $BehindHttpsProxy) {
    throw "HTTPS requiere -BehindHttpsProxy y un proxy corporativo existente que gestione el certificado."
}
if (-not $Https -and -not $AllowInternalHttp) {
    throw "HTTP no cifra las credenciales. Para una prueba interna vuelva a ejecutar con -AllowInternalHttp; para produccion use HTTPS."
}
if ($BehindHttpsProxy -and -not $Https) {
    throw "-BehindHttpsProxy solo puede usarse con una PublicUrl https://."
}
if (-not $Https -and $Uri.Port -ne $Port) {
    throw "El puerto de PublicUrl ($($Uri.Port)) debe coincidir con -Port ($Port) en modo HTTP."
}

$Origin = "{0}://{1}" -f $Uri.Scheme, $Uri.Authority
$BindHost = if ($Https) { "127.0.0.1" } else { "0.0.0.0" }
$AllowedHosts = @($Uri.Host, "127.0.0.1", "localhost") | Select-Object -Unique

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $StaticRoot, $LogDirectory, $WorkDirectory | Out-Null
$ProjectAccess = "${ServiceAccount}:(OI)(CI)RX"
& icacls $ProjectRoot /grant $ProjectAccess /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo conceder lectura del proyecto a $ServiceAccount."
}
$RuntimeAcl = @(
    "${ServiceAccount}:(OI)(CI)M",
    "SYSTEM:(OI)(CI)F",
    "BUILTIN\Administrators:(OI)(CI)F"
)
& icacls $RuntimeRoot /inheritance:r /grant:r $RuntimeAcl /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron asignar permisos de ejecucion en $RuntimeRoot a $ServiceAccount."
}
$WorkAcl = @(
    "${ServiceAccount}:(OI)(CI)M",
    "SYSTEM:(OI)(CI)F",
    "BUILTIN\Administrators:(OI)(CI)F"
)
& icacls $WorkDirectory /inheritance:r /grant:r $WorkAcl /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron proteger los archivos de trabajo para $ServiceAccount."
}
$SecretsAcl = @(
    "${ServiceAccount}:(OI)(CI)R",
    "SYSTEM:(OI)(CI)F",
    "BUILTIN\Administrators:(OI)(CI)F"
)
& icacls $SecretsDirectory /inheritance:r /grant:r $SecretsAcl /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron proteger los secretos para $ServiceAccount."
}

# Solo modifica configuracion publica; nunca lee ni escribe contrasenas.
Set-EnvValue -Name "DEBUG" -Value "False"
Set-EnvValue -Name "ALLOWED_HOSTS" -Value ($AllowedHosts -join ",")
Set-EnvValue -Name "CSRF_TRUSTED_ORIGINS" -Value $Origin
Set-EnvValue -Name "PORTAL_PUBLIC_URL" -Value $Origin
Set-EnvValue -Name "PORTAL_BIND_HOST" -Value $BindHost
Set-EnvValue -Name "PORTAL_PORT" -Value ([string]$Port)
Set-EnvValue -Name "PORTAL_THREADS" -Value ([string]$Threads)
Set-EnvValue -Name "STATIC_ROOT" -Value ($StaticRoot.Replace("\", "/"))
Set-EnvValue -Name "SECURE_SSL_REDIRECT" -Value ($(if ($Https) { "True" } else { "False" }))
Set-EnvValue -Name "SESSION_COOKIE_SECURE" -Value ($(if ($Https) { "True" } else { "False" }))
Set-EnvValue -Name "CSRF_COOKIE_SECURE" -Value ($(if ($Https) { "True" } else { "False" }))
Set-EnvValue -Name "TRUST_X_FORWARDED_PROTO" -Value ($(if ($Https) { "True" } else { "False" }))
Set-EnvValue -Name "SECURE_HSTS_SECONDS" -Value ($(if ($Https) { "31536000" } else { "0" }))
Set-EnvValue -Name "SECURE_HSTS_PRELOAD" -Value "False"

Write-Host "Comprobando Oracle y Django antes de registrar el inicio automatico..."
Set-Location $ProjectRoot
& $Python "run.py" "check"
if ($LASTEXITCODE -ne 0) {
    throw "La validacion del portal fallo. No se registro la tarea automatica."
}

$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$Arguments = @(
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy Bypass",
    "-File `"$Runner`"",
    "-BindHost `"$BindHost`"",
    "-Port $Port",
    "-Threads $Threads",
    "-RuntimeRoot `"$RuntimeRoot`""
) -join " "
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$TaskPasswordSecure = Read-Host "Contrasena Windows de $ServiceAccount para el inicio automatico (no se mostrara)" -AsSecureString
$TaskPasswordBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($TaskPasswordSecure)
try {
    $TaskPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TaskPasswordBstr)
    if ([string]::IsNullOrWhiteSpace($TaskPasswordPlain)) {
        throw "La contrasena Windows no puede estar vacia."
    }
    if ($Existing) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        $StopDeadline = (Get-Date).AddSeconds(20)
        while ((Get-ScheduledTask -TaskName $TaskName).State -eq "Running" -and (Get-Date) -lt $StopDeadline) {
            Start-Sleep -Milliseconds 500
        }
        if ((Get-ScheduledTask -TaskName $TaskName).State -eq "Running") {
            throw "La tarea existente no pudo detenerse. No se reemplazo su configuracion."
        }
    }
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Description "Portal Claro - Gestion de No Conformidades" `
            -Action $Action `
            -Trigger $Trigger `
            -Settings $Settings `
            -User $ServiceAccount `
            -Password $TaskPasswordPlain `
            -RunLevel Highest `
            -Force | Out-Null
    }
    catch {
        if ($Existing) { Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
        throw "No se pudo registrar la tarea con $ServiceAccount. Revise la contrasena y el permiso 'Iniciar sesion como trabajo por lotes'. $($_.Exception.Message)"
    }
}
finally {
    if ($TaskPasswordBstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TaskPasswordBstr)
    }
    $TaskPasswordPlain = $null
    $TaskPasswordSecure = $null
}

$CurrentRule = Get-NetFirewallRule -DisplayName $FirewallRule -ErrorAction SilentlyContinue
if (-not $Https) {
    if ($CurrentRule) {
        $CurrentRule | Set-NetFirewallRule -Direction Inbound -Action Allow -Enabled True -Profile Domain | Out-Null
        $CurrentRule | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $Port | Out-Null
        $CurrentRule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $AllowedRemoteAddress | Out-Null
    }
    else {
        New-NetFirewallRule `
            -DisplayName $FirewallRule `
            -Group "Portal NC" `
            -Direction Inbound `
            -Action Allow `
            -Enabled True `
            -Profile Domain `
            -Protocol TCP `
            -LocalPort $Port `
            -RemoteAddress $AllowedRemoteAddress | Out-Null
    }
}
elseif ($CurrentRule) {
    $CurrentRule | Disable-NetFirewallRule | Out-Null
}

Start-ScheduledTask -TaskName $TaskName
$Deadline = (Get-Date).AddSeconds(90)
do {
    Start-Sleep -Seconds 2
    $Task = Get-ScheduledTask -TaskName $TaskName
    if ($Task.State -eq "Running" -and (Test-TcpPort -HostName "127.0.0.1" -TargetPort $Port)) { break }
    if ($Task.State -eq "Ready") { break }
} while ((Get-Date) -lt $Deadline)

$Task = Get-ScheduledTask -TaskName $TaskName
if ($Task.State -ne "Running" -or -not (Test-TcpPort -HostName "127.0.0.1" -TargetPort $Port)) {
    $LatestLog = Get-ChildItem $LogDirectory -Filter "portal-*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($LatestLog) {
        Write-Host "Ultimas lineas de $($LatestLog.FullName):"
        Get-Content $LatestLog.FullName -Tail 30
    }
    throw "La tarea se registro, pero el portal no abrio el puerto $Port. Revise el log."
}

Write-Host ""
Write-Host "Portal publicado correctamente."
Write-Host "URL: $Origin"
Write-Host "Tarea automatica: $TaskName"
Write-Host "Cuenta: $ServiceAccount"
Write-Host "Logs: $LogDirectory"
if ($Https) {
    Write-Host "Waitress esta limitado a localhost; el proxy HTTPS debe dirigir el trafico a 127.0.0.1:$Port."
}
else {
    Write-Warning "La publicacion HTTP esta limitada por firewall, pero no cifra las credenciales. Usela solo dentro de la red corporativa."
}
Write-Host "Administracion: powershell.exe -NoProfile -ExecutionPolicy Bypass -File `".\scripts\gestionar_portal_windows.ps1`" -Action status"
