# Lanza el servidor del chat local sin ventana y, cuando ya responde de verdad,
# abre http://127.0.0.1:<Port> una sola vez en el navegador predeterminado.
#
# - Reutiliza un servidor que ya este escuchando en <Port>.
# - Espera hasta <WaitSeconds> comprobando /api/health y la pagina /.
# - Si no responde, no abre nada y deja una linea en logs\start.log.
# - Con -Stop detiene el servidor arrancado por este script (PID file).
param(
    [string]$PythonExe = '',
    [int]$Port = 8765,
    [int]$WaitSeconds = 10,
    [string]$LogFile = '',
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'SilentlyContinue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $dir
$script = Join-Path $dir 'server.py'
$page = Join-Path $dir 'chat.html'
$pidFile = Join-Path $dir "chat-$Port.pid"
$url = "http://127.0.0.1:$Port/"

if (-not $LogFile) {
    $LogFile = Join-Path $root 'logs\start.log'
}
$logDir = Split-Path -Parent $LogFile

function Write-StartLog([string]$text) {
    try {
        if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -LiteralPath $LogFile -Value "$stamp [chat-local] $text" -Encoding UTF8
    } catch {
        # El log es best-effort: nunca debe impedir arrancar o abrir el chat.
    }
}

function Test-PortOpen([int]$port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-ChatPid([int]$port) {
    try {
        $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($connection) { return [int]$connection.OwningProcess }
    } catch {
        # Fallback para equipos sin Get-NetTCPConnection.
        try {
            $line = netstat -ano | Select-String ":$port\s" | Select-String 'LISTENING' |
                Select-Object -First 1
            if ($line) {
                $parts = ($line.ToString().Trim() -split '\s+')
                return [int]$parts[-1]
            }
        } catch { }
    }
    return $null
}

function Get-ChatHealth([int]$port) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        if ([int]$response.StatusCode -ne 200) { return $null }
        return ($response.Content | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Test-ChatReady([int]$port) {
    $health = Get-ChatHealth $port
    if (-not $health -or $health.ok -ne $true -or $health.app -ne 'chat-local') {
        return $false
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 2
        return ([int]$response.StatusCode -eq 200 -and $response.Content -match '<title>Chat de IAs</title>')
    } catch {
        return $false
    }
}

if ($Stop) {
    $serverPid = $null
    if (Test-Path -LiteralPath $pidFile) {
        try { $serverPid = [int]((Get-Content -LiteralPath $pidFile -Raw).Trim()) } catch { }
    }
    if (-not $serverPid) { $serverPid = Get-ChatPid $Port }
    if ($serverPid) {
        $info = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid" -ErrorAction SilentlyContinue
        if ($info -and $info.CommandLine -like '*server.py*' -and $info.CommandLine -like '*chat-local*') {
            Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
            Write-StartLog "servidor del chat detenido (pid $serverPid)."
        } else {
            Write-StartLog "pid $serverPid no parece ser chat-local\server.py; no se detiene."
        }
    }
    if (Test-Path -LiteralPath $pidFile) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

$WaitSeconds = [Math]::Max(1, [Math]::Min(60, $WaitSeconds))

if (-not (Test-Path -LiteralPath $script)) {
    Write-StartLog "server.py no encontrado en $script; no se abre el navegador."
    exit 1
}
if (-not (Test-Path -LiteralPath $page)) {
    Write-StartLog "chat.html no encontrado en $page; no se abre el navegador."
    exit 1
}

$started = $false
$startError = ''
if (-not (Test-PortOpen $Port)) {
    if (-not $PythonExe) {
        Write-StartLog "PythonExe vacio y el puerto $Port esta cerrado; no se abre el navegador."
        exit 1
    }
    $previousPort = $env:CHAT_LOCAL_PORT
    $env:CHAT_LOCAL_PORT = "$Port"
    try {
        $proc = Start-Process -FilePath $PythonExe `
            -ArgumentList ('"' + $script + '" --port ' + $Port) `
            -WorkingDirectory $dir -WindowStyle Hidden -PassThru
        if ($proc) {
            Set-Content -LiteralPath $pidFile -Value $proc.Id -Encoding ASCII
            $started = $true
            Write-StartLog "servidor iniciado (pid $($proc.Id), puerto $Port)."
        }
    } catch {
        $startError = $_.Exception.Message
    } finally {
        $env:CHAT_LOCAL_PORT = $previousPort
    }
} else {
    $existingPid = Get-ChatPid $Port
    if ($existingPid) {
        Set-Content -LiteralPath $pidFile -Value $existingPid -Encoding ASCII
        Write-StartLog "puerto $Port ya abierto; se reutiliza el servidor (pid $existingPid)."
    } else {
        Write-StartLog "puerto $Port ya abierto; no se pudo leer el PID, se reutiliza igualmente."
    }
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-ChatReady $Port) {
        if ($NoBrowser) {
            Write-StartLog "chat listo en ${url}; navegador no abierto (NoBrowser)."
            exit 0
        }
        try {
            Start-Process -FilePath $url
            Write-StartLog "navegador abierto en ${url}."
            exit 0
        } catch {
            Write-StartLog "no se pudo abrir el navegador en ${url}: $($_.Exception.Message)"
            exit 1
        }
    }
    Start-Sleep -Milliseconds 250
}

$detail = ''
if ($startError) {
    $detail = "; error al iniciar: $startError"
} else {
    $health = Get-ChatHealth $Port
    if ($health -and $health.app -ne 'chat-local') {
        $detail = "; el puerto lo ocupa otra aplicacion ($($health.app))"
    }
}
Write-StartLog "sin respuesta valida en ${url} tras $WaitSeconds s; no se abre el navegador$detail"
exit 1
