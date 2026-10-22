param(
    [string]$ServiceAccount = $env:USERNAME
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecretsDir = Join-Path $ProjectRoot "secrets"
$SecretPath = Join-Path $SecretsDir "correo_ssh_password.txt"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

$Secure = Read-Host "Contraseña SSH del servidor de correo (no se mostrará)" -AsSecureString
$Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
try {
    $Plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
    if ([string]::IsNullOrWhiteSpace($Plain)) {
        throw "La contraseña SSH no puede estar vacía."
    }
    [IO.File]::WriteAllText($SecretPath, $Plain, [Text.UTF8Encoding]::new($false))
}
finally {
    if ($Bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
    }
    $Plain = $null
}

& icacls $SecretPath /inheritance:r /grant:r "${ServiceAccount}:(R,W)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron restringir los permisos de $SecretPath."
}

Write-Host "Se creó el secreto SSH y se protegió para $ServiceAccount. Su valor no fue mostrado."
Write-Host "Complete las variables CORREO_* y PORTAL_PUBLIC_URL en .env antes de habilitar el envío."
Write-Host "Después ejecute scripts\preparar_identidad_correo_windows.ps1 como administrador."
