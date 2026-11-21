# SPDX-License-Identifier: GPL-3.0-or-later
# Prepara un entorno Python 3.12 portable en runtime\python\ dentro de la
# carpeta del proyecto, sin instalar nada en Windows ni pedir permisos de admin.
#
# Instala las dependencias (websockets y watchdog) extrayendo sus wheels (.whl)
# oficiales de PyPI directamente con PowerShell, por lo que funciona incluso si
# Windows Defender tiene "Acceso controlado a carpetas" activado en Documentos.
#
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File preparar_portable.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File preparar_portable.ps1 -Force
param(
    [string]$PythonVersion = '3.12.10',
    [switch]$Force,
    [switch]$SkipPackages,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $Root 'runtime'
$PyDir = Join-Path $RuntimeDir 'python'
$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("zs_portable_" + $PID)
$PyExe = Join-Path $PyDir 'python.exe'
$SitePkgs = Join-Path $PyDir 'Lib\site-packages'

function Say([string]$msg) {
    if (-not $Quiet) { Write-Host $msg }
}

# 1. Asegurar workspace_wake y copiar *.example.json si faltan las configs locales
$wakeDir = Join-Path $Root 'workspace_wake'
if (-not (Test-Path -LiteralPath $wakeDir)) {
    New-Item -ItemType Directory -Path $wakeDir -Force | Out-Null
}
$examplePairs = @(
    @('pc_agent_config.example.json', 'pc_agent_config.json'),
    @('pc_agent_config.restricted.example.json', 'pc_agent_config.restricted.json'),
    @('despertar_config.example.json', 'despertar_config.json')
)
foreach ($pair in $examplePairs) {
    $src = Join-Path $Root $pair[0]
    $dst = Join-Path $Root $pair[1]
    if ((Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $dst)) {
        Copy-Item -LiteralPath $src -Destination $dst
        Say "[portable] Configuracion inicial creada desde $($pair[0]) -> $($pair[1])"
    }
}

# 2. Comprobar si runtime\python ya esta listo
function Test-PortableReady {
    if (-not (Test-Path -LiteralPath $PyExe)) { return $false }
    try {
        if ($SkipPackages) {
            & $PyExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" *> $null
            return ($LASTEXITCODE -eq 0)
        }
        & $PyExe -c "import websockets, watchdog" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

if (-not $Force -and (Test-PortableReady)) {
    $ver = (& $PyExe --version 2>&1 | Out-String).Trim()
    Say "[portable] Ya esta listo: $PyExe ($ver)"
    exit 0
}

# 3. Determinar arquitectura
$archTag = 'amd64'
$wheelPlat = 'win_amd64'
$procArch = ($env:PROCESSOR_ARCHITECTURE + '').ToUpperInvariant()
$procArchW64 = ($env:PROCESSOR_ARCHITEW6432 + '').ToUpperInvariant()
if ($procArch -eq 'ARM64' -or $procArchW64 -eq 'ARM64') {
    $archTag = 'arm64'
    $wheelPlat = 'win_arm64'
} elseif (-not [System.Environment]::Is64BitOperatingSystem) {
    $archTag = 'win32'
    $wheelPlat = 'win32'
}

$pyMajorMinor = ($PythonVersion -split '\.')[0..1] -join ''
$cpTag = "cp$pyMajorMinor"
$zipName = "python-$PythonVersion-embed-$archTag.zip"
$pyUrl = "https://www.python.org/ftp/python/$PythonVersion/$zipName"

# TLS 1.2 obligatorio en Windows 10 / PowerShell 5.1
try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

function Download-File([string]$url, [string]$dest) {
    $prev = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 120
    } finally {
        $ProgressPreference = $prev
    }
}

function Install-PyPiWheel([string]$pkgName) {
    Say "[portable] Descargando $pkgName desde PyPI..."
    $meta = Invoke-RestMethod -Uri "https://pypi.org/pypi/$pkgName/json" -TimeoutSec 30
    $wheels = @($meta.urls | Where-Object { $_.packagetype -eq 'bdist_wheel' })
    if ($wheels.Count -eq 0) {
        throw "No se encontraron wheels para $pkgName en PyPI."
    }
    # Prioridad: wheel nativo cp312 + plataforma -> py3 plataforma -> py3-none-any
    $chosen = $wheels | Where-Object { $_.filename -like "*-$cpTag-*$wheelPlat.whl" } | Select-Object -First 1
    if (-not $chosen) {
        $chosen = $wheels | Where-Object { $_.filename -like "*-py3-none-$wheelPlat.whl" } | Select-Object -First 1
    }
    if (-not $chosen) {
        $chosen = $wheels | Where-Object { $_.filename -like "*-py3-none-any.whl" } | Select-Object -First 1
    }
    if (-not $chosen) {
        throw "No se encontro un wheel compatible para $pkgName ($cpTag/$wheelPlat)."
    }
    $whlZip = Join-Path $TmpDir ($chosen.filename + '.zip')
    Download-File $chosen.url $whlZip
    if ($chosen.digests -and $chosen.digests.sha256) {
        $actual = (Get-FileHash -LiteralPath $whlZip -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected = ($chosen.digests.sha256 + '').ToLowerInvariant()
        if ($actual -ne $expected) {
            throw "SHA-256 no coincide para $($chosen.filename)"
        }
    }
    Say "[portable] Instalando $($chosen.filename) en runtime\python\Lib\site-packages..."
    Expand-Archive -LiteralPath $whlZip -DestinationPath $SitePkgs -Force
}

if ($Force -and (Test-Path -LiteralPath $PyDir)) {
    Say "[portable] Limpiando runtime\python anterior..."
    Remove-Item -LiteralPath $PyDir -Recurse -Force
}

New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
New-Item -ItemType Directory -Path $PyDir -Force | Out-Null

try {
    if (-not (Test-Path -LiteralPath $PyExe)) {
        $zipPath = Join-Path $TmpDir $zipName
        Say "[portable] Descargando Python $PythonVersion portable ($archTag)..."
        Download-File $pyUrl $zipPath
        Say "[portable] Extrayendo en runtime\python\..."
        Expand-Archive -LiteralPath $zipPath -DestinationPath $PyDir -Force
    }

    # Configurar python*._pth sin BOM para habilitar site-packages y la raiz del proyecto
    $pthFile = Get-ChildItem -LiteralPath $PyDir -Filter 'python*._pth' | Select-Object -First 1
    if (-not $pthFile) {
        throw "No se encontro el archivo python*._pth dentro de $PyDir"
    }
    $zipStdlib = (Get-ChildItem -LiteralPath $PyDir -Filter 'python*.zip' | Select-Object -First 1)
    $zipEntry = if ($zipStdlib) { $zipStdlib.Name } else { "python$pyMajorMinor.zip" }
    $pthLines = @(
        $zipEntry,
        '.',
        '..',
        '..\..',
        'Lib\site-packages',
        'import site'
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($pthFile.FullName, ($pthLines -join "`r`n") + "`r`n", $utf8NoBom)

    New-Item -ItemType Directory -Path $SitePkgs -Force | Out-Null

    if (-not $SkipPackages) {
        Install-PyPiWheel 'websockets'
        Install-PyPiWheel 'watchdog'
    }

    # Verificacion final (sin escribir bytecode por si CFA protege la carpeta)
    $prevNoPyc = $env:PYTHONDONTWRITEBYTECODE
    $env:PYTHONDONTWRITEBYTECODE = '1'
    try {
        if ($SkipPackages) {
            & $PyExe -c "import sys; print('Python portable OK:', sys.version.split()[0])"
        } else {
            & $PyExe -c "import sys, websockets, watchdog, mailbox_store; print('Python portable OK:', sys.version.split()[0], '| websockets', websockets.__version__)"
        }
        if ($LASTEXITCODE -ne 0) {
            throw "La verificacion de Python portable fallo."
        }
    } finally {
        $env:PYTHONDONTWRITEBYTECODE = $prevNoPyc
    }

    # Avisar si Windows Defender CFA bloquea escrituras de runtime\python\python.exe en esta ruta
    $cfaTest = Join-Path $Root 'logs\.portable_write_test'
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $logsDir = Join-Path $Root 'logs'
        if (-not (Test-Path -LiteralPath $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
        & $PyExe -c "import pathlib, sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()" $cfaTest *> $null
        if ($LASTEXITCODE -ne 0) {
            Say "[portable] AVISO: Windows Defender (Acceso controlado a carpetas) impide a runtime\python\python.exe escribir en esta carpeta."
            Say "[portable]        En otro PC (o moviendo el proyecto fuera de Documentos, p. ej. C:\ZeroScriptModify) funcionara sin restricciones."
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }

    Say "[portable] Listo. Puedes copiar toda la carpeta del proyecto a cualquier PC sin Python."
} finally {
    if (Test-Path -LiteralPath $TmpDir) {
        Remove-Item -LiteralPath $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
exit 0
