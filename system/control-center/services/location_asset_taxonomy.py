"""One versioned location-only category and surface material contract.

Category IDs and material keys are stable persistence values. Group/label order is
explicit authoring presentation, not a database identity or Workspace path.
"""
from __future__ import annotations

CATEGORY_GROUPS = (
    ('flora', 'Flora', ('tree', 'bush', 'flower', 'rock')),
    ('structure', 'Structure', ('light', 'fence', 'ladder', 'bridge', 'pillar', 'post')),
    ('prop', 'Prop', ('prop', 'decoration', 'building')),
)
CATEGORIES = tuple(item for _, _, names in CATEGORY_GROUPS for item in names)
CATEGORY_LABELS = {name: name.capitalize() for name in CATEGORIES}

# material key -> label / Roblox physical material / semantic sound family.
# "default" does NOT rewrite an existing MeshPart.Material (legacy safe).
MATERIALS = (
    ('default', 'Default · unchanged', '', 'generic'),
    ('wood', 'Wood', 'Wood', 'wood'),
    ('stone', 'Stone', 'Slate', 'stone'),
    ('rock', 'Rock', 'Rock', 'stone'),
    ('concrete', 'Concrete', 'Concrete', 'stone'),
    ('brick', 'Brick', 'Brick', 'stone'),
    ('metal', 'Metal', 'Metal', 'metal'),
    ('glass', 'Glass', 'Glass', 'glass'),
    ('plastic', 'Plastic', 'Plastic', 'plastic'),
    ('fabric', 'Fabric', 'Fabric', 'fabric'),
    ('foliage', 'Foliage', 'LeafyGrass', 'foliage'),
    ('grass', 'Grass', 'Grass', 'foliage'),
    ('soil', 'Soil', 'Ground', 'earth'),
    ('sand', 'Sand', 'Sand', 'earth'),
    ('ice', 'Ice', 'Ice', 'ice'),
)
MATERIAL_BY_ID = {key: dict(id=key, label=label, robloxMaterial=roblox, soundFamily=sound)
                  for key, label, roblox, sound in MATERIALS}

def surface_material(value):
    value = str(value or 'default').strip().lower()
    if value not in MATERIAL_BY_ID:
        raise ValueError('invalid Location Asset surface material')
    return value

def options():
    return {
        'categoryGroups': [dict(id=key, label=label, categories=[
            {'id':cat, 'label':CATEGORY_LABELS[cat], 'group':key} for cat in names])
            for key,label,names in CATEGORY_GROUPS],
        'categories': [dict(id=cat, label=CATEGORY_LABELS[cat], group=key)
                       for key,_,names in CATEGORY_GROUPS for cat in names],
        'surfaceMaterials': [MATERIAL_BY_ID[key].copy() for key,_,_,_ in MATERIALS],
    }
