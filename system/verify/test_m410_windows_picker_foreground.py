"""M410: all Windows browser-triggered pickers have an owned foreground dialog."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from services import native_pickers, windows_explorer


class WindowsPickerForegroundTests(TestCase):
    def test_all_native_file_and_folder_choosers_share_topmost_modal_owner(self):
        methods = (
            native_pickers.choose_character_fbx,
            native_pickers.choose_character_atlas,
            native_pickers.choose_weapon_fbx,
            native_pickers.choose_location_asset_fbx,
            native_pickers.choose_location_asset_texture,
            native_pickers.choose_monster_fbx,
            native_pickers.choose_monster_textures,
            native_pickers.choose_weapon_textures,
            native_pickers.choose_animation_folder,
            native_pickers.choose_real_estate_texture,
            native_pickers.choose_real_estate_fbx,
            native_pickers.choose_character_animation_file,
        )
        with mock.patch.object(native_pickers.shutil, 'which', return_value='powershell.exe'), \
             mock.patch.object(native_pickers.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='C:\\media\\a.fbx\n', stderr='')) as run:
            for method in methods:
                with self.subTest(picker=method.__name__):
                    method()
                    args, kwargs = run.call_args
                    self.assertEqual(args[0][:3], ['powershell.exe', '-NoProfile', '-STA'])
                    self.assertIn('Show-Game1Dialog', args[0][4])
                    self.assertIn('$owner.TopMost = $true', args[0][4])
                    self.assertIn('$dialog.ShowDialog($owner)', args[0][4])
                    self.assertIn('$owner.Dispose()', args[0][4])
                    self.assertIn('(Show-Game1Dialog $dialog)', args[0][4])
                    self.assertNotIn('$dialog.ShowDialog()', args[0][4])
                    self.assertEqual(kwargs['timeout'], 120)
            self.assertEqual(run.call_count, len(methods))

    def test_cancel_does_not_change_picker_result_contract(self):
        with mock.patch.object(native_pickers.shutil, 'which', return_value='powershell.exe'), \
             mock.patch.object(native_pickers.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')):
            self.assertEqual(native_pickers.choose_location_asset_fbx(), '')
            self.assertEqual(native_pickers.choose_weapon_textures(), [])
            self.assertEqual(native_pickers.choose_animation_folder(), '')

    def test_multi_select_keeps_separator_and_picker_initial_directory(self):
        with mock.patch.object(native_pickers.shutil, 'which', return_value='powershell.exe'), \
             mock.patch.object(native_pickers.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='a.png\x1fb.png\n', stderr='')) as run:
            self.assertEqual(native_pickers.choose_monster_textures(), ['a.png', 'b.png'])
            native_pickers.choose_real_estate_texture('C:\\models\\tree.fbx')
            self.assertEqual(run.call_args.kwargs['env']['GAME1_REAL_ESTATE_PICKER_INITIAL_PATH'], 'C:\\models\\tree.fbx')

    def test_show_in_folder_targets_only_matching_explorer_window(self):
        with mock.patch.object(windows_explorer.os, 'name', 'nt'), \
             mock.patch.object(windows_explorer.os, 'startfile', create=True) as startfile, \
             mock.patch.object(windows_explorer.shutil, 'which', return_value='powershell.exe'), \
             mock.patch.object(windows_explorer.subprocess, 'run') as run:
            windows_explorer.reveal_folder('C:\\art')
            startfile.assert_called_once_with('C:\\art')
            args, kwargs = run.call_args
            self.assertEqual(kwargs['env']['GAME1_REVEAL_FOLDER'], 'C:\\art')
            self.assertIn('OrdinalIgnoreCase', args[0][-1])
            self.assertIn('SetForegroundWindow', args[0][-1])
            self.assertIn('SetWindowPos', args[0][-1])

    def test_explorer_focus_failure_does_not_cancel_opened_folder(self):
        with mock.patch.object(windows_explorer.os, 'name', 'nt'), \
             mock.patch.object(windows_explorer.os, 'startfile', create=True) as startfile, \
             mock.patch.object(windows_explorer.shutil, 'which', return_value='powershell.exe'), \
             mock.patch.object(windows_explorer.subprocess, 'run', side_effect=OSError('shell unavailable')):
            windows_explorer.reveal_folder('C:\\art')
            startfile.assert_called_once()
