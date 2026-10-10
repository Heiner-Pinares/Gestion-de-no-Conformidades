param(
    [string]$ServiceAccount = $env:USERNAME
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecretsDir = Join-Path $ProjectRoot "secrets"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

function Write-SecureSecret {
    param([string]$Path, [string]$Prompt)
    $Secure = Read-Host $Prompt -AsSecureString
    $Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        $Plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
        if ([string]::IsNullOrWhiteSpace($Plain)) { throw "El secreto no puede estar vacío." }
        [IO.File]::WriteAllText($Path, $Plain, [Text.UTF8Encoding]::new($false))
    }
    finally {
        if ($Bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr) }
        $Plain = $null
    }
}

$OraclePath = Join-Path $SecretsDir "oracle_password.txt"
Write-SecureSecret -Path $OraclePath -Prompt "Contraseña Oracle (no se mostrará)"

$DjangoPath = Join-Path $SecretsDir "django_secret_key.txt"
if (-not (Test-Path $DjangoPath)) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    & $Python -c "import secrets, pathlib; pathlib.Path(r'$DjangoPath').write_text(secrets.token_urlsafe(64), encoding='utf-8')"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar SECRET_KEY." }
}

foreach ($Path in @($OraclePath, $DjangoPath)) {
    & icacls $Path /inheritance:r /grant:r "${ServiceAccount}:(R,W)" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron restringir los permisos de $Path." }
}

Write-Host "Secretos creados y protegidos para $ServiceAccount. Sus valores no fueron mostrados."
