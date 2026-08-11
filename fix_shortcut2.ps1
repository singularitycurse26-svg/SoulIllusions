$appDir = "C:\Users\hawpe\CascadeProjects\SoulIllusions"
$icon = "$appDir\soulillusions_icon.ico"
$batFile = "$appDir\launch.bat"
$desktop = "$env:USERPROFILE\OneDrive\Desktop\SoulIllusions AI Video Maker.lnk"

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($desktop)
$Shortcut.TargetPath = $batFile
$Shortcut.WorkingDirectory = $appDir
$Shortcut.IconLocation = "$icon, 0"
$Shortcut.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut.WindowStyle = 7  # minimized (server runs in background, browser opens)
$Shortcut.Save()
Write-Host "Desktop shortcut updated to use launch.bat"

$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\SoulIllusions AI Video Maker.lnk"
$Shortcut2 = $WshShell.CreateShortcut($startMenu)
$Shortcut2.TargetPath = $batFile
$Shortcut2.WorkingDirectory = $appDir
$Shortcut2.IconLocation = "$icon, 0"
$Shortcut2.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut2.WindowStyle = 7
$Shortcut2.Save()
Write-Host "Start Menu shortcut updated too"
