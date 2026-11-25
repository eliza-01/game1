"""M479: Character Creation authoring contract; data validated before Luau export.

The five ordered views are captured in Roblox Studio. Options includes a portable
fallback, so camera presentation survives streaming and compiled Runtime Places.
"""
from __future__ import annotations
from copy import deepcopy
from math import isfinite
import re

VIEW_NAMES = ('SelectionOverview', 'MaleFullBody', 'FemaleFullBody', 'MaleFace', 'FemaleFace')
VIEW_ROLES = ('overview', 'male_body', 'female_body', 'male_face', 'female_face')

CAMERA_VIEWS = {'SelectionOverview': {'cframe': [194.504593, -304.755432, 170.894653, -0.192445204, -0.290456295, 0.937336683, 3.72528985e-09, 0.955191374, 0.295989007, -0.981307685, 0.0569616668, -0.183822021], 'fov': 70}, 'MaleFullBody': {'cframe': [182.015625, -308.425964, 170.331039, -0.708430588, -0.162659898, 0.68678087, 7.45057971e-09, 0.973080039, 0.230468094, -0.705780566, 0.163270652, -0.689359605], 'fov': 70}, 'FemaleFullBody': {'cframe': [185.124832, -309.109985, 166.462067, 0.395562619, -0.160015583, 0.904392183, 3.72529074e-09, 0.984705806, 0.174225584, -0.91843909, -0.0689171255, 0.389512748], 'fov': 70}, 'MaleFace': {'cframe': [180.331024, -308.415009, 172.346603, -0.723042011, -0.109602585, 0.682053983, -0.0, 0.987333477, 0.158659428, -0.690804124, 0.114717431, -0.713883519], 'fov': 70}, 'FemaleFace': {'cframe': [182.726929, -308.539276, 166.062881, 0.310615152, -0.11110054, 0.944020629, -0.0, 0.993145883, 0.116882019, -0.950535774, -0.036305327, 0.308486134], 'fov': 70}}

FACE_MATERIALS = ('Plastic', 'Slate', 'Fabric', 'SmoothPlastic', 'Sandstone', 'Grass', 'LeafyGrass', 'Concrete')
MATERIAL_GROUPS = ('hair', 'eyes', 'eyebrows', 'head')

REACTION_GROUPS = ('atk', 'bow', 'clap', 'hi', 'laugh', 'sad', 'sp_wait', 'unaware', 'victory', 'waiting', 'yes')

DEFAULTS = {
    'enabled': False,  # opt-in until Studio Play composition is verified
    'useStudioAnchors': True,
    'transitionSeconds': 0.9,
    'faceTransitionSeconds': 0.65,
    'desktopPanelWidthPx': 460,
    'mobilePanelWidthPx': 330,
    'spawnPoints': {
        'male': {'position': [179.449, -314.025, 176.096], 'rotationDegrees': [0.0, -35.501, 0.0]},
        'female': {'position': [177.64, -314.025, 167.78], 'rotationDegrees': [0.0, -93.433, 0.0]},
    },
    'useStudioSpawnMarkers': False,
    'colorPresets': {
        'hair': ['#161616', '#765034', '#E2BD83'],
        'eyes': ['#3A6483', '#638B5A', '#795333'],
        'eyebrows': ['#161616', '#765034', '#E2BD83'],
    },
    'materialChoices': {group: list(FACE_MATERIALS) for group in MATERIAL_GROUPS},
    'animations': {'chancePercent': 35, 'weights': {group: 100 for group in REACTION_GROUPS}},
    'views': CAMERA_VIEWS,
}


def normalize_character_creation(value, base=None):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('characterCreation: unknown settings')
    data = deepcopy(DEFAULTS if base is None else normalize_character_creation(base))
    for key, item in value.items():
        if key in ('enabled', 'useStudioAnchors', 'useStudioSpawnMarkers'):
            if type(item) is not bool:
                raise ValueError(f'characterCreation.{key}: expected boolean')
        elif key in ('transitionSeconds', 'faceTransitionSeconds'):
            if type(item) not in (int, float) or not isfinite(item) or not 0.1 <= item <= 5:
                raise ValueError(f'characterCreation.{key}: expected 0.1..5')
            item = float(item)
        elif key in ('desktopPanelWidthPx', 'mobilePanelWidthPx'):
            if type(item) is not int or not 240 <= item <= 540:
                raise ValueError(f'characterCreation.{key}: expected integer 240..540')
        elif key == 'animations':
            if not isinstance(item, dict) or set(item) != {'chancePercent', 'weights'}:
                raise ValueError('characterCreation.animations: chancePercent/weights required')
            chance, weights = item['chancePercent'], item['weights']
            if type(chance) is not int or not 0 <= chance <= 100:
                raise ValueError('characterCreation.animations.chancePercent: integer 0..100 required')
            if not isinstance(weights, dict) or set(weights) != set(REACTION_GROUPS) or any(
                    type(weight) is not int or not 0 <= weight <= 100 for weight in weights.values()):
                raise ValueError('characterCreation.animations.weights: integer 0..100 for each reaction required')
            item = {'chancePercent': chance, 'weights': {group: weights[group] for group in REACTION_GROUPS}}
        elif key == 'colorPresets':
            if not isinstance(item, dict) or set(item) != {'hair', 'eyes', 'eyebrows'}:
                raise ValueError('characterCreation.colorPresets: hair/eyes/eyebrows required')
            for channel, colors in item.items():
                if not isinstance(colors, list) or len(colors) != 3 or any(
                        not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)
                        for color in colors):
                    raise ValueError(f'characterCreation.colorPresets.{channel}: three hex colors required')
            item = {channel: [color.upper() for color in colors] for channel, colors in item.items()}
        elif key == 'materialChoices':
            allowed = set(FACE_MATERIALS)
            if not isinstance(item, dict) or set(item) != set(MATERIAL_GROUPS):
                raise ValueError('characterCreation.materialChoices: hair/eyes/eyebrows/head required')
            if any(not isinstance(materials, list) or not 1 <= len(materials) <= 8
                   or any(not isinstance(m, str) or m not in allowed for m in materials)
                   or len(materials) != len(set(materials))
                   or 'Plastic' not in materials for materials in item.values()):
                raise ValueError('characterCreation.materialChoices: valid unique Roblox materials including Plastic required')
            item = {channel: list(materials) for channel, materials in item.items()}
        elif key == 'spawnPoints':
            if not isinstance(item, dict) or set(item) != {'male', 'female'}:
                raise ValueError('characterCreation.spawnPoints: male/female required')
            points = {}
            for gender, row in item.items():
                if not isinstance(row, dict) or set(row) != {'position', 'rotationDegrees'}:
                    raise ValueError('characterCreation.spawnPoints: position/rotationDegrees required')
                coords = {}
                for field in ('position', 'rotationDegrees'):
                    values = row[field]
                    if not isinstance(values, list) or len(values) != 3 or any(
                            type(v) not in (int, float) or not isfinite(v) or abs(v) > 100000 for v in values):
                        raise ValueError('characterCreation.spawnPoints: three finite coordinates required')
                    coords[field] = [float(v) for v in values]
                points[gender] = coords
            item = points
        elif key == 'views':
            if not isinstance(item, dict) or set(item) != set(VIEW_NAMES):
                raise ValueError('characterCreation.views: exactly five authored cameras required')
            normalized = {}
            for name in VIEW_NAMES:
                row = item[name]
                if not isinstance(row, dict) or set(row) != {'cframe', 'fov'}:
                    raise ValueError(f'characterCreation.views.{name}: cframe/fov required')
                numbers = row['cframe']
                if not isinstance(numbers, list) or len(numbers) != 12 or any(
                        type(x) not in (int, float) or not isfinite(x) or abs(x) > 1e7 for x in numbers):
                    raise ValueError(f'characterCreation.views.{name}: 12 finite cframe numbers required')
                fov = row['fov']
                if type(fov) not in (int, float) or not isfinite(fov) or not 25 <= fov <= 100:
                    raise ValueError(f'characterCreation.views.{name}: fov 25..100 required')
                # Reject degenerate rotation matrices before they reach the client.
                x, y, z = numbers[3:6], numbers[6:9], numbers[9:12]
                norm = lambda a: sum(p*p for p in a)
                dot = lambda a,b: sum(p*q for p,q in zip(a,b))
                determinant = (x[0]*(y[1]*z[2]-y[2]*z[1])
                    - x[1]*(y[0]*z[2]-y[2]*z[0])
                    + x[2]*(y[0]*z[1]-y[1]*z[0]))
                if abs(determinant - 1) > 0.06 or any(
                        abs(norm(a) - 1) > 0.06 for a in (x,y,z)) or any(
                        abs(dot(a,b)) > 0.06 for a,b in ((x,y),(x,z),(y,z))):
                    raise ValueError(f'characterCreation.views.{name}: rotation must be orthonormal')
                normalized[name] = {'cframe': [float(n) for n in numbers], 'fov': float(fov)}
            item = normalized
        data[key] = item
    return data
