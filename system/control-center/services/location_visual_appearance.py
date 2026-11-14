"""Location Asset visual appearance, independent from semantic sound material.

Only Roblox BasePart-compatible Enum.Material members are offered. The list
mirrors https://create.roblox.com/docs/reference/engine/enums/Material
(Air/Water are Terrain-only, ForceField requires a texture and is not a valid
textureless choice).  No MaterialVariant/MaterialService assets are assumed.
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
    if mode not in ('atlas', 'material'):
        raise ValueError('appearanceMode must be atlas or material')
    material = str(material or 'SmoothPlastic').strip()
    if material not in BASEPART_MATERIALS:
        raise ValueError('visualMaterial must be a supported Roblox BasePart Enum.Material')
    if mode == 'material' and material == 'ForceField':
        raise ValueError('ForceField requires a texture; choose an atlas or another material')
    color = str(color or '#FFFFFF').strip().upper()
    if not re.fullmatch(r'#[0-9A-F]{6}', color):
        raise ValueError('visualColor must be a #RRGGBB color')
    return mode, material, color


def options() -> list[dict]:
    return [{'id': name, 'label': name, 'requiresTexture': name == 'ForceField'}
            for name in BASEPART_MATERIALS]
