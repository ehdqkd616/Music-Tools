' 더블클릭으로 Studio 서버 관리 GUI를 콘솔 창 없이 실행한다.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = scriptDir & "\tools\server-manager\app.py"

Set shell = CreateObject("WScript.Shell")
shell.Run """pythonw"" """ & appPath & """", 0, False
