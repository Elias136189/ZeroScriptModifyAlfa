# Oculta la ventana de consola que lo lanzo (start.bat) pasados N segundos.
# Solo la oculta si el bridge de ZeroScript ya esta escuchando (puerto 17613);
# si el bridge fallo, la deja visible para que se pueda leer el error.
# Con -Mostrar vuelve a mostrar la ventana (start.bat lo usa cuando el bridge termina).
param(
    [int]$Segundos = 10,
    [switch]$Mostrar,
    [int]$PuertoBridge = 17613
)

Add-Type -Namespace Win -Name Native -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@

$h = [Win.Native]::GetConsoleWindow()
if ($h -eq [IntPtr]::Zero) { exit 0 }

if ($Mostrar) {
    [Win.Native]::ShowWindow($h, 5) | Out-Null   # SW_SHOW
    exit 0
}

Start-Sleep -Seconds $Segundos

$bridgeVivo = Get-NetTCPConnection -LocalPort $PuertoBridge -State Listen -ErrorAction SilentlyContinue
if ($bridgeVivo) {
    [Win.Native]::ShowWindow($h, 0) | Out-Null   # SW_HIDE
}
