param(
    [ValidateSet("start", "stop", "restart", "status", "logs")]
    [string]$Action = "status",
    [string]$TaskName = "PortalNC",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$RuntimeRoot = "$env:ProgramData\PortalNC"
)

$ErrorActionPreference = "Stop"
$LogDirectory = Join-Path $RuntimeRoot "logs"

function Get-PortalTask {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $Task) {
        throw "No existe la tarea $TaskName. Ejecute scripts\publicar_portal_windows.ps1 como administrador."
    }
    return $Task
}

function Wait-PortalStopped {
    $Deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        $State = (Get-ScheduledTask -TaskName $TaskName).State
    } while ($State -eq "Running" -and (Get-Date) -lt $Deadline)
    if ($State -eq "Running") { throw "La tarea no se detuvo dentro de 20 segundos." }
}

switch ($Action) {
    "start" {
        $Task = Get-PortalTask
        if ($Task.State -ne "Running") { Start-ScheduledTask -TaskName $TaskName }
        Write-Host "Inicio solicitado para $TaskName."
    }
    "stop" {
        $Task = Get-PortalTask
        if ($Task.State -eq "Running") {
            Stop-ScheduledTask -TaskName $TaskName
            Wait-PortalStopped
        }
        Write-Host "$TaskName esta detenido."
    }
    "restart" {
        $Task = Get-PortalTask
        if ($Task.State -eq "Running") {
            Stop-ScheduledTask -TaskName $TaskName
            Wait-PortalStopped
        }
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Reinicio solicitado para $TaskName."
    }
    "status" {
        $Task = Get-PortalTask
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "Tarea: $TaskName"
        Write-Host "Estado: $($Task.State)"
        Write-Host "Ultimo inicio: $($Info.LastRunTime)"
        Write-Host "Ultimo resultado: $($Info.LastTaskResult)"
        Write-Host "Puerto local: $Port"
        Write-Host "Logs: $LogDirectory"
    }
    "logs" {
        Get-PortalTask | Out-Null
        $LatestLog = Get-ChildItem $LogDirectory -Filter "portal-*.log" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $LatestLog) { throw "Todavia no existe un log en $LogDirectory." }
        Write-Host "Log: $($LatestLog.FullName)"
        Get-Content $LatestLog.FullName -Tail 100
    }
}
