$python = "$env:APPDATA\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe"
$appDir = "C:\Users\hawpe\CascadeProjects\SoulIllusions"
$icon = "$appDir\soulillusions_icon.ico"
$desktop = "$env:USERPROFILE\OneDrive\Desktop\SoulIllusions AI Video Maker.lnk"

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($desktop)
$Shortcut.TargetPath = $python
$Shortcut.Arguments = "server.py"
$Shortcut.WorkingDirectory = $appDir
$Shortcut.IconLocation = "$icon, 0"
$Shortcut.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut.Save()
Write-Host "Shortcut updated with direct Python path"

# Also update Start Menu
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\SoulIllusions AI Video Maker.lnk"
$Shortcut2 = $WshShell.CreateShortcut($startMenu)
$Shortcut2.TargetPath = $python
$Shortcut2.Arguments = "server.py"
$Shortcut2.WorkingDirectory = $appDir
$Shortcut2.IconLocation = "$icon, 0"
$Shortcut2.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut2.Save()
Write-Host "Start Menu shortcut updated too"
