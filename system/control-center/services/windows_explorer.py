"""Bring an explicitly opened Explorer folder in front without pinning it there."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


_FOCUS_FOLDER = r'''
$target = [System.IO.Path]::GetFullPath($env:GAME1_REVEAL_FOLDER).TrimEnd([char]'\')
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class Game1ExplorerFocus {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int cx, int cy, uint flags);
}
'@
$shell = New-Object -ComObject Shell.Application
for ($attempt = 0; $attempt -lt 12; $attempt++) {
    foreach ($window in $shell.Windows()) {
        try {
            $uri = [Uri]$window.LocationURL
            if (!$uri.IsFile) { continue }
            $folder = [System.IO.Path]::GetFullPath($uri.LocalPath).TrimEnd([char]'\')
            if (-not [string]::Equals($folder, $target, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $handle = [IntPtr]::new([long]$window.HWND)
            [void][Game1ExplorerFocus]::ShowWindow($handle, 9)
            [void][Game1ExplorerFocus]::SetWindowPos($handle, [IntPtr]::new(-1), 0, 0, 0, 0, 0x43)
            [void][Game1ExplorerFocus]::SetForegroundWindow($handle)
            [void][Game1ExplorerFocus]::SetWindowPos($handle, [IntPtr]::new(-2), 0, 0, 0, 0, 0x43)
            return
        } catch { continue }
    }
    [System.Threading.Thread]::Sleep(100)
}
'''


def reveal_folder(path: str | Path) -> None:
    """Open a known folder and best-effort focus exactly that Explorer window.

    Opening the folder remains successful even when ShellWindows enumeration is
    unavailable. Never put arbitrary Explorer windows permanently topmost.
    """
    if os.name != 'nt':
        raise ValueError('Show in folder is supported by the Windows Host Agent')
    folder = os.fspath(path)
    os.startfile(folder)
    powershell = shutil.which('powershell.exe') or shutil.which('powershell')
    if not powershell:
        return
    env = os.environ.copy()
    env['GAME1_REVEAL_FOLDER'] = folder
    try:
        subprocess.run(
            [powershell, '-NoProfile', '-STA', '-Command', _FOCUS_FOLDER],
            capture_output=True, text=True, env=env, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        # Explorer was opened; only foreground activation failed.
        pass
