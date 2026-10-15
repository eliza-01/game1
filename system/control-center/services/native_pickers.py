"""Native Windows file and folder dialogs for authoring tools.

This adapter is intentionally separate from HTTP, data stores and Studio Bridge.
A cancelled dialog still returns an empty path/list, preserving the UI contract.
"""
import os
import shutil
import subprocess


def _powershell_picker(script: str, extra_env: dict | None = None) -> str:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("powershell was not found for the native picker")
    picker_env = os.environ.copy()
    if extra_env:
        picker_env.update({str(key): str(value) for key, value in extra_env.items()})
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
        env=picker_env,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "picker failed").strip())
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def choose_character_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose character fbx'
$dialog.Filter = 'fbx character model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )



def choose_weapon_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose weapon fbx'
$dialog.Filter = 'fbx weapon model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_location_asset_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose location asset fbx'
$dialog.Filter = 'fbx location asset model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_location_asset_texture() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose location asset texture'
$dialog.Filter = 'texture (*.png;*.jpg;*.jpeg)|*.png;*.jpg;*.jpeg|png texture (*.png)|*.png|jpeg texture (*.jpg;*.jpeg)|*.jpg;*.jpeg'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_monster_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose monster fbx'
$dialog.Filter = 'fbx monster model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_monster_textures() -> list[str]:
    raw = _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose monster textures'
$dialog.Filter = 'monster textures (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'
$dialog.Multiselect = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output ($dialog.FileNames -join [char]31)
}
'''
    )
    return [item for item in raw.split(chr(31)) if item]


def choose_weapon_textures() -> list[str]:
    raw = _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose weapon textures'
$dialog.Filter = 'weapon textures (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'
$dialog.Multiselect = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output ($dialog.FileNames -join [char]31)
}
'''
    )
    return [item for item in raw.split(chr(31)) if item]

def choose_animation_folder(initial_path: str = "") -> str:
    initial_path = str(initial_path or "").strip().strip('"')
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'game1 · choose folder containing exported animations (.rbxm/.rbxmx)'
$dialog.ShowNewFolderButton = $false
$initialPath = $env:GAME1_ANIMATION_PICKER_INITIAL_PATH
if ($initialPath -and [System.IO.Directory]::Exists($initialPath)) {
    $dialog.SelectedPath = $initialPath
}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
'''
        , {"GAME1_ANIMATION_PICKER_INITIAL_PATH": initial_path}
    )
