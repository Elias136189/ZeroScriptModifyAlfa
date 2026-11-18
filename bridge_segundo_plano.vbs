' Lanza el bridge de ZeroScript en segundo plano (sin ventana).
' Doble clic para arrancar. Si ya hay un bridge en el puerto 17613, no lanza otro.
' Salida del bridge: logs\bridge_stdout.log
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FolderExists(dir & "\logs") Then fso.CreateFolder(dir & "\logs")

' Comprobar si el puerto 17613 ya esta en uso
Set ex = sh.Exec("cmd /c netstat -aon | findstr :17613 | findstr LISTENING")
salida = ex.StdOut.ReadAll()
If Len(Trim(salida)) > 0 Then
  MsgBox "El bridge ya esta corriendo en el puerto 17613. No se lanzo otro.", 64, "ZeroScript"
  WScript.Quit 0
End If

cmd = "cmd /c cd /d """ & dir & """ && set ZS_BRIDGE_EXTENSION_ID=ljkcldlijdibhfookemkeeefpmgijcge&& py -3 bridge.py >> logs\bridge_stdout.log 2>&1"
sh.Run cmd, 0, False
MsgBox "Bridge lanzado en segundo plano. Revisa logs\bridge_stdout.log si algo falla.", 64, "ZeroScript"
