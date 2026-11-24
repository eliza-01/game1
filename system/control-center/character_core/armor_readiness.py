"""Read-only armor authoring completeness, independent of persistence and rig assembly.

A set is a set of optional logical slots. Once a slot is authored it must
resolve for BOTH genders: explicitly or via one complete compatible unisex
variant. Drafts can be saved while their counterpart is being authored.
This report does not assert bind-pose compatibility; ArmorCatalog.resolve
remains the authoritative check for a concrete rig and gender.
"""
from __future__ import annotations

GENDERS = ('male', 'female')


def _choice(piece, gender):
    variants = piece['variants']
    # An explicitly authored partial override may not silently fall back.
    if gender in variants:
        return gender, variants[gender]
    if 'unisex' in variants:
        return 'unisex', variants['unisex']
    return '', None


def _problem(piece, gender, mesh_index, appearances, atlases):
    source, variant = _choice(piece, gender)
    if variant is None:
        return 'variant'
    mesh_id = variant.get('meshPartId')
    appearance_id = variant.get('appearanceId')
    if not mesh_id:
        return 'mesh'
    if not appearance_id:
        return 'appearance'
    mesh = mesh_index.get(mesh_id)
    if not mesh or mesh.get('slot') != piece['slot'] or gender not in mesh.get('allowedGenders', ()):
        return 'mesh_compatibility'
    if not str(mesh.get('model_asset_id') or '').isdigit() or mesh.get('published_revision') != mesh.get('revision'):
        return 'mesh_publication'
    appearance = appearances.get(appearance_id)
    if appearance is None:
        return 'appearance'
    atlas = atlases.get(appearance.get('atlas_variant_id'))
    if not atlas or not atlas.get('current') or atlas.get('replacementPending') or not str(atlas.get('published_id') or '').isdigit():
        return 'atlas_publication'
    return ''


def describe_set(armor_set, meshes, appearances, atlases):
    """Return an additive, JSON-serializable two-gender completeness report."""
    mesh_index = {mesh['id']: mesh for mesh in meshes}
    appearance_index = {appearance['id']: appearance for appearance in appearances}
    atlas_index = {atlas['id']: atlas for atlas in atlases}
    result = {gender: {'complete': True, 'assigned': 0, 'required': len(armor_set['pieces']), 'missing': []}
              for gender in GENDERS}
    slots = {}
    for piece in armor_set['pieces']:
        slot = piece['slot']
        slot_status = {}
        for gender in GENDERS:
            source, _variant = _choice(piece, gender)
            reason = _problem(piece, gender, mesh_index, appearance_index, atlas_index)
            slot_status[gender] = {'ready': not reason, 'source': source, 'reason': reason}
            if reason:
                result[gender]['complete'] = False
                result[gender]['missing'].append({'slot': slot, 'reason': reason})
            else:
                result[gender]['assigned'] += 1
        slots[slot] = slot_status
    return {'complete': all(result[gender]['complete'] for gender in GENDERS),
            'genders': result, 'slots': slots}
