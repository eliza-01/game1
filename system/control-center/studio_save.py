from __future__ import annotations

from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import threading
import time


_ALLOWED_STUDIO_EXE = {"robloxstudiobeta.exe", "robloxstudio.exe"}
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_KEYEVENTF_KEYUP = 0x0002
_VK_CONTROL = 0x11
_VK_S = 0x53


def _foreground_studio_window() -> tuple[int, str, str]:
    if os.name != "nt":
        raise RuntimeError("automatic Studio save is only available on the Windows host agent")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("no foreground window is available for Studio save")

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        raise RuntimeError("could not resolve the foreground process for Studio save")

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        raise RuntimeError("could not inspect the foreground process for Studio save")

    try:
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(capacity)):
            raise RuntimeError("could not read the foreground process path for Studio save")
        executable = Path(buffer.value).name.lower()
    finally:
        kernel32.CloseHandle(process)

    if executable not in _ALLOWED_STUDIO_EXE:
        raise RuntimeError(
            f"Roblox Studio must be the active window when Save Assets Data is pressed (foreground: {executable or 'unknown'})"
        )

    title_length = user32.GetWindowTextLengthW(hwnd)
    title_buffer = ctypes.create_unicode_buffer(max(title_length + 1, 2))
    user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
    return int(hwnd), title_buffer.value, executable


def _send_ctrl_s(hwnd_value: int) -> None:
    time.sleep(0.20)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = wintypes.HWND(hwnd_value)
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
    user32.keybd_event.restype = None
    if not user32.IsWindow(hwnd):
        return

    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(_VK_CONTROL, 0, 0, 0)
    user32.keybd_event(_VK_S, 0, 0, 0)
    user32.keybd_event(_VK_S, 0, _KEYEVENTF_KEYUP, 0)
    user32.keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, 0)


def request_active_studio_save() -> dict:
    """Schedule Studio's native Ctrl+S after the HTTP response returns.

    The game1 authoring place is normally opened from a local .rbxl file, where
    AssetService:SavePlaceAsync cannot save because game.PlaceId is 0. The host
    agent is already a Windows-local companion process, so invoke Studio's own
    save command instead of using a cloud place API.
    """

    hwnd, title, executable = _foreground_studio_window()
    threading.Thread(target=_send_ctrl_s, args=(hwnd,), daemon=True).start()
    return {
        "requested": True,
        "method": "studio-native-ctrl-s",
        "windowTitle": title,
        "process": executable,
    }
