"""Version 1 character component names. No filesystem, Blender or UI dependencies."""
import re

VERSION = 1
TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
BODY = re.compile(r"^(?P<set>[a-z][a-z0-9]*(?:_[a-z0-9]+)*)_(?P<slot>upper|lower|gloves|boots)$")
HEAD = re.compile(r"^(?P<slot>head|hair)_(?P<number>[0-9]{2,})_(?P<gender>male|female|common)$")
FACE = re.compile(r"^(?P<slot>eyes|eyebrows)_(?P<number>[0-9]{2,})(?P<effect>_spiral)?$")


def parse_part(name):
    if not isinstance(name, str) or len(name) > 96 or not TOKEN.fullmatch(name):
        raise ValueError(f"{name!r}: expected lower_case_snake_case without .001")
    match = HEAD.fullmatch(name)
    if match:
        if int(match['number']) < 1 or (match['slot'] == 'head' and match['gender'] == 'common'):
            raise ValueError(f"{name}: head requires male/female; index starts at 01")
        return dict(id=name, slot=match['slot'], set_id='', gender=match['gender'], role='part')
    match = FACE.fullmatch(name)
    if match and int(match['number']) > 0:
        if match['effect'] and match['slot'] != 'eyes':
            raise ValueError('only eyes support the spiral effect suffix')
        return dict(id=name, slot=match['slot'], set_id='', gender='common',
                    role='effect' if match['effect'] else 'part')
    match = BODY.fullmatch(name)
    if match:
        return dict(id=name, slot=match['slot'], set_id=match['set'], gender='common', role='part')
    raise ValueError(f"{name}: use <set>_upper/lower/gloves/boots, head_01_male/female, "
                     'hair_01_male/female/common, eyes_01 or eyebrows_01')


def rig_id(armature_name):
    suffix = '_armature'
    if not armature_name.endswith(suffix):
        raise ValueError('main rig must be named <profile>_armature, for example human_armature')
    key = armature_name[:-len(suffix)]
    if not TOKEN.fullmatch(key) or len(key) > 64:
        raise ValueError('invalid rig profile name')
    return key


def skeleton_matches(expected, actual, tolerance=1e-5):
    left = {b['name']: b for b in expected}; right = {b['name']: b for b in actual}
    if len(left) != len(expected) or len(right) != len(actual) or left.keys() != right.keys():
        raise ValueError('rig bone set changed; register a new profile instead')
    for name, bone in left.items():
        other = right[name]
        a, b = bone['matrix'], other['matrix']
        if bone['parent'] != other['parent'] or len(a) != 16 or len(b) != 16 or any(abs(x-y)>tolerance for x,y in zip(a,b)):
            raise ValueError(f'bind pose/parent changed for {name}; register a new rig profile')
