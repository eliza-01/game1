"""Resource availability in diagnostic archives, not a general missing-file waiver."""
import json


def require_payloads(test, root, paths):
    missing = [path for path in paths if not (root / path).is_file()]
    if not missing:
        return
    marker = root / '_dump/model_files.json'
    if marker.is_file():
        manifest = json.loads(marker.read_text(encoding='utf-8-sig'))
        omitted = {entry['path'].replace('\\', '/') for entry in manifest['files']}
        if all(path in omitted for path in missing):
            test.skipTest('Payload intentionally omitted in diagnostic archive: ' + ', '.join(missing))
    test.fail('Required payload missing: ' + ', '.join(missing))
