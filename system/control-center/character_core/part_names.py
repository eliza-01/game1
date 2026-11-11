"""Canonical Character MeshPart identity (geometry, not armor or appearance).

All modular MeshParts, including independent left/right face islands, share
<rig_profile>_<male|female|common>_mNNN_<slot>.
"""
import re

VERSION = 2
TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
SLOTS = ('upper', 'lower', 'gloves', 'boots', 'head', 'eye_l', 'eye_r',
         'eyebrow_l', 'eyebrow_r', 'hair')
MESH = re.compile(
    r"^(?P<profile>[a-z][a-z0-9]*(?:_[a-z0-9]+)*)_"
    r"(?P<gender>male|female|common)_m(?P<number>[0-9]{3})_"
    r"(?P<slot>upper|lower|gloves|boots|head|eye_l|eye_r|eyebrow_l|eyebrow_r|hair)"
    r"(?P<effect>_(?:spiral|happy|happy_sharp_caret|happy_thick_caret|nausea_wave))?$"
)


def parse_part(name):
    if not isinstance(name, str) or len(name) > 96 or not TOKEN.fullmatch(name):
        raise ValueError(f"{name!r}: expected lower_case_snake_case without .001")
    match = MESH.fullmatch(name)
    if not match or int(match['number']) < 1:
        raise ValueError(f"{name}: use human_male_m001_upper / human_female_m001_head / "
                         "human_common_m001_eye_l / human_female_m001_eyebrow_r / "
                         "human_female_m001_hair (m001 starts at 001)")
    if match['effect'] and not match['slot'].startswith('eye_'):
        raise ValueError(f'{name}: eye effect suffix is valid only for eye_l/eye_r')
    family = name[:match.start('slot')-1]
    if match['effect']:
        # Effects are optional visual assets, not face assembly slots.
        role = 'effect'
    else:
        role = 'part'
    return dict(id=name, slot=match['slot'], set_id='', mesh_family_id=family,
                rig_profile_id=match['profile'], gender=match['gender'], role=role)


HAIR_EXTRA = re.compile(r"^(?P<root>.+_hair)_extra_(?P<number>[0-9]{2})$")


def parse_hair_extra(name):
    """A contained rigid mesh, not an independently registerable Character part."""
    if not isinstance(name, str) or len(name) > 115 or not TOKEN.fullmatch(name):
        return None
    match = HAIR_EXTRA.fullmatch(name)
    if not match or int(match['number']) < 1:
        return None
    try:
        root = parse_part(match['root'])
    except ValueError:
        return None
    if root['slot'] != 'hair' or root['role'] != 'part':
        return None
    return dict(root_id=root['id'], channel='extra_' + match['number'])


def hair_color_channels(part):
    """One primary color plus the authored extras, never arbitrary channels."""
    root = part['name']
    names = [extra['name'] for extra in part.get('extras', [])]
    if len(names) != len(set(names)):
        raise ValueError(root + ': duplicate hair extras')
    channels = ['primary']
    for name in names:
        extra = parse_hair_extra(name)
        if not extra or extra['root_id'] != root:
            raise ValueError(root + ': invalid hair extra ' + name)
        channels.append(extra['channel'])
    return channels


def default_allowed_genders(part):
    """Name-derived Inspect suggestion ONLY; DB compatibility stays explicit."""
    return ['male', 'female'] if part['gender'] == 'common' else [part['gender']]


def rig_id(armature_name):
    suffix = '_armature'
    if not armature_name.endswith(suffix):
        raise ValueError('main rig must be named <profile>_armature, for example human_armature')
    key = armature_name[:-len(suffix)]
    if not TOKEN.fullmatch(key) or len(key) > 64:
        raise ValueError('invalid rig profile name')
    return key


def rig_family_and_gender(rig_key):
    """Resolve the family of either a shared or gender-specific rig profile.

    `human_armature` is shared; `human_female_armature` and
    `human_male_armature` are separate bind profiles of the human family.
    This is naming policy, NOT proof that those rigs share a bind pose.
    """
    if not isinstance(rig_key, str) or not TOKEN.fullmatch(rig_key):
        raise ValueError('invalid rig profile ID')
    for suffix in ('_male', '_female'):
        if rig_key.endswith(suffix):
            return rig_key[:-len(suffix)], suffix[1:]
    return rig_key, None


def part_matches_source_rig(part, rig_key):
    """Check an FBX mesh name against the actual primary Armature.

    `common` is permissible on an authored gendered rig, but that alone
    does not prove it can be equipped on another rig: the resolver must
    also check bind compatibility when changing rig profiles.
    """
    family, rig_gender = rig_family_and_gender(rig_key)
    return (part['rig_profile_id'] == family
            and (rig_gender is None or part['gender'] in (rig_gender, 'common')))


def skeleton_matches(expected, actual, tolerance=1e-5):
    left = {b['name']: b for b in expected}; right = {b['name']: b for b in actual}
    if len(left) != len(expected) or len(right) != len(actual) or left.keys() != right.keys():
        raise ValueError('rig bone set changed; register a new profile instead')
    for name, bone in left.items():
        other = right[name]
        a, b = bone['matrix'], other['matrix']
        if bone['parent'] != other['parent'] or len(a) != 16 or len(b) != 16 or any(abs(x-y)>tolerance for x,y in zip(a,b)):
            raise ValueError(f'bind pose/parent changed for {name}; register a new rig profile')


def rigid_pivot_mount_for_part(name):
    """Only a rigless hair part may be mounted by its authored mesh pivot."""
    try:
        part = parse_part(name)
    except ValueError:
        return ''
    return 'hair_mount' if part['slot'] == 'hair' and part['role'] == 'part' else ''
