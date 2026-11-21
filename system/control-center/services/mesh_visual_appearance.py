"""Shared MeshPart visual material policy for Real Estate and Location Assets.

All Roblox BasePart-compatible Enum.Material members are offered. The list
mirrors https://create.roblox.com/docs/reference/engine/enums/Material
(Air/Water are Terrain-only; ForceField needs a UV-mapped texture and is not
offered for textureless Material + Color). No MaterialVariant assets are assumed.
Both editor APIs use options() and both stores use validated().
"""
from __future__ import annotations
import re

BASEPART_MATERIALS = (
    'Plastic', 'SmoothPlastic', 'Neon', 'Wood', 'WoodPlanks', 'Marble',
    'Basalt', 'Slate', 'CrackedLava', 'Concrete', 'Limestone', 'Granite',
    'Pavement', 'Brick', 'Pebble', 'Cobblestone', 'Rock', 'Sandstone',
    'CorrodedMetal', 'DiamondPlate', 'Foil', 'Metal', 'Grass',
    'LeafyGrass', 'Sand', 'Fabric', 'Snow', 'Mud', 'Ground', 'Asphalt',
    'Salt', 'Ice', 'Glacier', 'Glass', 'ForceField', 'Cardboard',
    'Carpet', 'CeramicTiles', 'ClayRoofTiles', 'RoofShingles',
    'Leather', 'Plaster', 'Rubber',
)


def validated(mode: object, material: object, color: object) -> tuple[str, str, str]:
    mode = str(mode or 'atlas').strip().lower()
    if mode not in ('atlas', 'material', 'material_atlas'):
        raise ValueError('appearanceMode must be atlas, material or material_atlas')
    material = str(material or 'Plastic').strip()
    if material not in BASEPART_MATERIALS:
        raise ValueError('visualMaterial must be a supported Roblox BasePart Enum.Material')
    if mode == 'material' and material == 'ForceField':
        raise ValueError('ForceField requires a texture; choose an atlas or another material')
    color = str(color or '#FFFFFF').strip().upper()
    if not re.fullmatch(r'#[0-9A-F]{6}', color):
        raise ValueError('visualColor must be a #RRGGBB color')
    return mode, material, color


def uses_atlas(mode: str) -> bool:
    return mode in ('atlas', 'material_atlas')


def uses_material(mode: str) -> bool:
    return mode in ('material', 'material_atlas')


def options() -> list[dict]:
    return [{'id': name, 'label': name, 'requiresTexture': name == 'ForceField'}
            for name in BASEPART_MATERIALS]
