"""Read-only comparison of Rojo-managed Luau sources against a saved XML Place."""
from pathlib import Path
import hashlib
import json

SCRIPT_CLASSES = {'Script', 'LocalScript', 'ModuleScript'}


def _source(value):
    return value.replace('\r\n', '\n').replace('\r', '\n').removeprefix('\ufeff')


def _class_name(path):
    name = path.name
    for suffix, cls in (('.server.luau', 'Script'), ('.client.luau', 'LocalScript'),
                        ('.server.lua', 'Script'), ('.client.lua', 'LocalScript'),
                        ('.luau', 'ModuleScript'), ('.lua', 'ModuleScript')):
        if name.endswith(suffix):
            return name[:-len(suffix)], cls
    return None


def expected_scripts(root):
    root = Path(root)
    project = root / 'default.project.json'
    if not project.is_file():
        raise ValueError('default.project.json is missing; cannot verify Runtime scripts')
    result = {}
    scopes = []

    def add(key, path, cls):
        if key in result:
            raise ValueError('Duplicate Rojo script path: ' + '.'.join(key))
        result[key] = (cls, _source(path.read_text(encoding='utf-8')))

    def directory(folder, key):
        for child in sorted(folder.iterdir()):
            if child.name.startswith('.'):
                continue
            if child.is_dir():
                directory(child, key + (child.name,))
            elif spec := _class_name(child):
                name, cls = spec
                add(key if name == 'init' else key + (name,), child, cls)

    def walk(node, key):
        if '$path' in node:
            folder = (root / node['$path']).resolve()
            if not folder.is_relative_to(root.resolve()) or not folder.is_dir():
                raise ValueError('Unsupported Rojo source mapping: ' + str(folder))
            scopes.append(key)
            directory(folder, key)
        for name, value in node.items():
            if not name.startswith('$') and isinstance(value, dict):
                walk(value, key + (name,))

    walk(json.loads(project.read_text(encoding='utf-8-sig'))['tree'], ())
    if not result:
        raise ValueError('No Rojo-managed scripts found; cannot verify Runtime scripts')
    return result, scopes


def verify_scripts(root, tree):
    expected, scopes = expected_scripts(root)
    found = {}
    errors = []

    def walk(parent, key):
        for item in parent.findall('Item'):
            name = item.findtext('./Properties/string[@name="Name"]') or ''
            # Root services may omit Name when it is the class default.
            path = key + (name or item.get('class', ''),)
            cls = item.get('class')
            if cls in SCRIPT_CLASSES and any(path[:len(scope)] == scope for scope in scopes):
                if path in found:
                    errors.append('duplicate ' + '.'.join(path))
                found[path] = item
            walk(item, path)

    walk(tree.getroot(), ())
    digest = hashlib.sha256()
    for key, (cls, source) in sorted(expected.items()):
        item = found.get(key)
        path = '.'.join(key)
        if item is None:
            errors.append('missing ' + path)
        elif item.get('class') != cls:
            errors.append('wrong class ' + path)
        else:
            prop = item.find('./Properties/ProtectedString[@name="Source"]')
            if prop is None:
                prop = item.find('./Properties/string[@name="Source"]')
            if prop is None or _source(prop.text or '') != source:
                errors.append('stale ' + path)
            if cls != 'ModuleScript' and (item.findtext('./Properties/bool[@name="Disabled"]') == 'true'
                                          or item.findtext('./Properties/bool[@name="Enabled"]') == 'false'):
                errors.append('disabled ' + path)
        digest.update(json.dumps([key, cls, source], ensure_ascii=False).encode('utf-8'))
    errors.extend('unexpected ' + '.'.join(key) for key in sorted(found.keys() - expected.keys()))
    if errors:
        raise ValueError(f'Runtime scripts differ from Rojo sources ({len(errors)}): '
                         + '; '.join(errors[:8]) + '. Rojo Sync, then Save to File as game1_runtime_source.rbxlx; rerun Preflight.')
    return {'scriptCount': len(expected), 'scriptSha256': digest.hexdigest()}
