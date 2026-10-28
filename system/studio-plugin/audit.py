#!/usr/bin/env python3
"""Read-only audit of Game1Bridge sources and the actual installed Studio plugin.

No Roblox Studio APIs, network access, account data or modifications are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PLUGIN_ROOT.parent.parent
EXPECTED_UI = {
    "Plots": ('StudioPlotsVisibility', 'StudioPlotsVisibility.new({', '"Game1Plots"'),
    "Markers": ('StudioMarkerVisibility', 'StudioMarkerVisibility.new(', '"Game1AuthoringMarkers"'),
    "DecoManager": ('DecoManager', 'DecoManager.new({', '"Game1DecoManager_v1"'),
}
EXPECTED_COMMANDS = {
    "Real Estate model sync": 'StudioModelLoadCommands',
    "Locations authoring": 'LocationCommands',
    "Monster/NPC spawns": 'StudioActorSpawnCommands',
    "Timeline editor": 'StudioTimelineEditorCommands',
    "Deco sync": 'StudioDecoSyncCommands',
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_bundle(path: Path) -> dict:
    """rbxmx stores scripts as XML Items; validate actual Item names, not substrings."""
    if not path.is_file():
        return {'status': 'missing', 'modules': [], 'main': False, 'plots_button': False}
    result = {'status': 'ok', 'size_bytes': path.stat().st_size, 'sha256': sha256(path)}
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as error:
        return {**result, 'status': 'unreadable-xml', 'error': str(error),
                'modules': [], 'main': False, 'plots_button': False}
    modules = set()
    main_source = ''
    scripts = []
    for item in tree.iter('Item'):
        kind = item.attrib.get('class', '')
        if kind not in ('Script', 'ModuleScript', 'LocalScript'):
            continue
        name = ''
        source = ''
        props = item.find('Properties')
        if props is not None:
            for prop in props:
                if prop.attrib.get('name') == 'Name':
                    name = prop.text or ''
                elif prop.attrib.get('name') == 'Source':
                    source = prop.text or ''
        if kind == 'ModuleScript':
            modules.add(name)
        else:
            scripts.append(name)
            if name == 'Main':
                main_source = source
    result['modules'] = sorted(modules)
    result['scripts'] = sorted(scripts)
    result['main'] = bool(main_source)
    result['plots_button'] = 'StudioPlotsVisibility.new({' in main_source
    result['studio_entrypoint'] = 'model bridge v24' in main_source
    return result


def audit(root: Path, installed: Path | None, plugins_dir: Path | None,
          *, generated_override: Path | None = None) -> dict:
    """Audit sources and a plugin bundle.

    For an installed-plugin audit the build is always ``root/generated``.
    Tests may explicitly inject an isolated, temporary generated artifact,
    so they never compare their fake installed plugin against the real build.
    """
    plugin_dir = root / 'system' / 'studio-plugin'
    manifest_path = plugin_dir / 'plugin.project.json'
    report: dict = {'status': 'ok', 'checks': [], 'plugins': {}}

    def check(name: str, success: bool, detail: str, *, warning: bool = False):
        level = 'OK' if success else ('WARN' if warning else 'FAIL')
        report['checks'].append({'name': name, 'status': level, 'detail': detail})
        if level == 'FAIL':
            report['status'] = 'failed'

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        module_entries = manifest['tree']['modules']
        expected = {name: details['$path'] for name, details in module_entries.items()
                    if name != '$className'}
    except (OSError, KeyError, TypeError, ValueError) as error:
        check('Rojo manifest', False, str(error))
        return report
    main_path = plugin_dir / manifest['tree']['Main']['$path']
    main = main_path.read_text(encoding='utf-8') if main_path.is_file() else ''
    all_source_modules = {p.stem for p in (plugin_dir / 'modules').glob('*.luau')}
    missing_files = [name for name, relative in expected.items()
                     if not (plugin_dir / relative).is_file()]
    unmapped = sorted(all_source_modules - set(expected))
    check('Rojo source inventory', not missing_files and not unmapped,
          f'{len(expected)} manifest modules; missing={missing_files}; unmapped={unmapped}')
    check('Main entrypoint', 'local toolbar = plugin:CreateToolbar("game1")' in main,
          'Game1Bridge.server.luau creates the game1 toolbar')
    for name, (module, constructor, button_id) in EXPECTED_UI.items():
        path = plugin_dir / expected.get(module, '')
        content = path.read_text(encoding='utf-8') if path.is_file() else ''
        ok = constructor in main and button_id in content and ':CreateButton(' in content
        check(f'Toolbar: {name}', ok,
              f'{module} in Rojo; bootstrap={constructor in main}; button={button_id in content}')
    for name, module in EXPECTED_COMMANDS.items():
        check(f'Command: {name}', module in expected and module in main,
              f'{module}: mapped={module in expected}, referenced={module in main}')

    installed_path = installed
    if installed_path is None and plugins_dir is not None:
        installed_path = plugins_dir / 'Game1Bridge.rbxmx'
    generated_path = generated_override if generated_override is not None else root / 'generated' / 'Game1Bridge.rbxmx'
    if installed_path is None:
        check('Installed plugin', False, 'LOCALAPPDATA is unavailable; use --installed', warning=True)
        return report

    built = inspect_bundle(installed_path)
    report['plugins']['installed'] = built
    check('Installed plugin exists', built['status'] != 'missing',
          'Game1Bridge.rbxmx exists' if built['status'] != 'missing' else 'Game1Bridge.rbxmx not found')
    if built['status'] == 'ok':
        absent = sorted(set(expected) - set(built['modules']))
        extra = sorted(set(built['modules']) - set(expected))
        check('Installed module inventory', not absent and not extra,
              f'{len(built["modules"])} installed; absent={absent}; extra={extra}')
        check('Installed Main & Plots initialization',
              built['main'] and built['plots_button'] and built['studio_entrypoint'],
              f'Main={built["main"]}; Plots wired={built["plots_button"]}; bridge v24={built["studio_entrypoint"]}')
    elif built['status'] == 'unreadable-xml':
        check('Installed plugin XML', False, built['error'])

    if generated_path.is_file() and installed_path.is_file():
        matches = sha256(generated_path) == sha256(installed_path)
        check('Generated / installed SHA256', matches,
              'identical bytes' if matches else 'different files: wrong/stale build may be installed')
    else:
        check('Generated / installed SHA256', False,
              'Generated build or installed copy unavailable for comparison', warning=True)

    if plugins_dir and plugins_dir.is_dir():
        candidates = sorted(p.name for p in plugins_dir.iterdir()
                            if p.is_file() and p.suffix.lower() in ('.rbxmx', '.rbxm'))
        report['plugins']['installed_names'] = candidates
        suspected = sorted(name for name in candidates
                           if name.lower().startswith('game1bridge') and name != 'Game1Bridge.rbxmx')
        check('Potential duplicate Game1Bridge files', not suspected,
              f'other Game1Bridge bundles: {suspected}', warning=True)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--installed', type=Path, default=None,
                        help='Specific installed .rbxmx (optional)')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args(argv)
    local_appdata = os.environ.get('LOCALAPPDATA')
    plugins_dir = Path(local_appdata) / 'Roblox' / 'Plugins' if local_appdata else None
    report = audit(args.project_root, args.installed, plugins_dir)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print('=== Game1Bridge Studio plugin: READ-ONLY audit ===')
        for record in report['checks']:
            print(f'[{record["status"]}] {record["name"]}: {record["detail"]}')
        installed = report['plugins'].get('installed', {})
        if installed.get('status') == 'ok':
            print('Installed SHA256:', installed['sha256'])
            print('Installed module count:', len(installed['modules']))
        print('Overall:', report['status'].upper())
        print('NOTE: Studio enablement and toolbar visibility cannot be read from disk.')
        print('Check Studio > Plugins > Manage Plugins, then Output for '
              '[game1 plugin] loaded and [game1][plots] toolbar ready.')
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
