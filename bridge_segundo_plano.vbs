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

' Busca primero Python portable dentro del proyecto (runtime\python\python.exe)
' para funcionar en PCs sin Python instalado; si no existe, usa py -3 o python.
pyCmd = ""
portablePy = dir & "\runtime\python\python.exe"
If fso.FileExists(portablePy) Then
  testCmd = """" & portablePy & """ -c ""import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()"" """ & dir & "\logs\.py_write_test"""
  If sh.Run(testCmd, 0, True) = 0 Then
    pyCmd = """" & portablePy & """"
  End If
End If
If pyCmd = "" Then
  If sh.Run("cmd /c where py >nul 2>nul", 0, True) = 0 Then
    pyCmd = "py -3"
  ElseIf sh.Run("cmd /c where python >nul 2>nul", 0, True) = 0 Then
    pyCmd = "python"
  End If
End If

If pyCmd = "" Then
  MsgBox "No se encontro Python ni runtime\python\python.exe. Ejecuta primero start.bat o preparar_portable.bat.", 48, "ZeroScript"
  WScript.Quit 1
End If

' bridge.py deriva automaticamente el ID de la extension desde manifest.json ("key" o ruta actual).
cmd = "cmd /c cd /d """ & dir & """ && " & pyCmd & " bridge.py >> logs\bridge_stdout.log 2>&1"
sh.Run cmd, 0, False
MsgBox "Bridge lanzado en segundo plano. Revisa logs\bridge_stdout.log si algo falla.", 64, "ZeroScript"
