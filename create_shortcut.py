"""
Create desktop shortcut for SoulIllusions AI Video Maker
Generates a custom icon and places a shortcut on the desktop.
"""
import os
import sys
import struct
from pathlib import Path

APP_DIR = Path(__file__).parent
ICON_PATH = APP_DIR / "soulillusions_icon.ico"
SHORTCUT_NAME = "SoulIllusions AI Video Maker"

def create_icon():
    """Create a simple ICO file with a purple/pink gradient S logo."""
    # Create a BMP-based ICO file (32x32)
    width, height = 32, 32
    
    # Build pixel data - purple to pink gradient with white S shape
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            # Gradient background
            t = (x + y) / (width + height)
            r = int(139 + (236 - 139) * t)  # purple to pink
            g = int(92 + (72 - 92) * t)
            b = int(246 + (153 - 246) * t)
            
            # Draw "S" shape (simplified)
            cx, cy = width // 2, height // 2
            dx, dy = abs(x - cx), abs(y - cy)
            
            # S shape: two arcs
            in_top_arc = (dy < 4 and dx < 6 and y < cy) or (dx < 2 and y < cy + 2 and y > cy - 4)
            in_bot_arc = (dy < 4 and dx < 6 and y >= cy) or (dx < 2 and y >= cy - 2 and y < cy + 4)
            in_middle = (abs(y - cy) < 2 and dx < 5)
            
            if in_top_arc or in_bot_arc or in_middle:
                r, g, b = 255, 255, 255
            
            row.append((r, g, b))
        pixels.append(row)
    
    # BMP data (bottom-up)
    bmp_data = bytearray()
    for y in range(height - 1, -1, -1):
        for x in range(width):
            r, g, b = pixels[y][x]
            bmp_data.extend([b, g, r, 0])  # BGRA
    
    # BMP info header
    bmp_header = struct.pack('<IIIHHIIIIII',
        40,           # header size
        width,        # width
        height * 2,   # height (doubled for ICO - AND mask)
        1,            # planes
        32,           # bits per pixel
        0,            # compression
        len(bmp_data),# image size
        0, 0,         # ppm x, y
        0, 0          # colors used, important
    )
    
    # AND mask (all zeros = fully opaque)
    and_mask = bytearray(width * height // 8)
    
    # ICO file
    ico_header = struct.pack('<HHH', 0, 1, 1)  # reserved, type=ICO, count=1
    
    image_data = bmp_header + bytes(bmp_data) + bytes(and_mask)
    
    dir_entry = struct.pack('<BBBBHHII',
        width if width < 256 else 0,   # width
        height if height < 256 else 0, # height
        0,                              # colors
        0,                              # reserved
        1,                              # planes
        32,                             # bits
        len(image_data),                # size
        6 + 16                          # offset (header + dir entry)
    )
    
    ico_data = ico_header + dir_entry + image_data
    
    ICON_PATH.write_bytes(ico_data)
    print(f"Icon created: {ICON_PATH}")

def create_shortcut():
    """Create a desktop shortcut using PowerShell."""
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    shortcut_path = desktop / f"{SHORTCUT_NAME}.lnk"
    target = str(APP_DIR / "launch.bat")
    icon = str(ICON_PATH)
    
    # Use PowerShell to create the shortcut
    ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target}"
$Shortcut.WorkingDirectory = "{APP_DIR}"
$Shortcut.IconLocation = "{icon}, 0"
$Shortcut.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut.Save()
Write-Host "Shortcut created: {shortcut_path}"
'''
    
    import subprocess
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print(f"Desktop shortcut created: {shortcut_path}")
    else:
        print(f"Error creating shortcut: {result.stderr}")
    
    # Also create a Start Menu shortcut
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_shortcut = start_menu / f"{SHORTCUT_NAME}.lnk"
    
    ps_script2 = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{start_shortcut}")
$Shortcut.TargetPath = "{target}"
$Shortcut.WorkingDirectory = "{APP_DIR}"
$Shortcut.IconLocation = "{icon}, 0"
$Shortcut.Description = "SoulIllusions AI Video Maker - 100% Free Text-to-Video"
$Shortcut.Save()
Write-Host "Start Menu shortcut created: {start_shortcut}"
'''
    
    result2 = subprocess.run(
        ["powershell", "-Command", ps_script2],
        capture_output=True, text=True
    )
    
    if result2.returncode == 0:
        print(f"Start Menu shortcut created: {start_shortcut}")
    else:
        print(f"Error creating start menu shortcut: {result2.stderr}")

if __name__ == "__main__":
    create_icon()
    create_shortcut()
    print("\nDone! Look for 'SoulIllusions AI Video Maker' on your desktop.")
