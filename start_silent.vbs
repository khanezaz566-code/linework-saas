Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\USER\.gemini\antigravity\scratch\linework"
WshShell.Run Chr(34) & "C:\Users\USER\AppData\Local\Python\bin\python.exe" & Chr(34) & " " & Chr(34) & "C:\Users\USER\.gemini\antigravity\scratch\linework\run.py" & Chr(34), 0, False
