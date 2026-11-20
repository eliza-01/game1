"""Shared offline MeshPart -> non-rendering Part conversion for Runtime drafts.

Keeps the original referent, all Bone/Attachment/effect/joint descendants and
physics CFrame/Size. The editable Place and authored meshes are never touched.
"""
from xml.etree import ElementTree as ET

MESH_PROPERTIES = {'MeshContent','MeshId','MeshID','TextureID','TextureContent',
    'CollisionFidelity','RenderFidelity','DoubleSided','MeshSize','HasSkinnedMesh',
    'FluidFidelity'}
# Preserve only properties supported by a Part. In particular preserve
# attributes, collision groups, scale, and original authored pivot.
PART_PROPERTIES = {'Name','CFrame','size','Size','PivotOffset','Anchored','CanCollide',
    'CanTouch','CanQuery','CastShadow','Massless','CollisionGroup',
    'CollisionGroupId','CustomPhysicalProperties','AttributesSerialize',
    'Tags','RootPriority','Locked','Transparency','Color3uint8','Color',
    'Material','MaterialVariant','Shape','Reflectance','BrickColor'}
RENDER_CHILDREN = {'SurfaceAppearance','WrapLayer','WrapTarget'}


def name(node):
    return next((p.text or '' for p in node.findall('./Properties/string')
        if p.get('name') == 'Name'), '')


def bool_property(node, property_name):
    values = [p for p in node.findall('./Properties/*') if p.get('name') == property_name]
    if len(values) != 1 or values[0].tag != 'bool' or (values[0].text or '').lower() not in ('true','false'):
        raise ValueError(f'{name(node)}: missing/invalid {property_name}')
    return values[0].text.lower() == 'true'


def convert(mesh, *, expected_collide=None, fill_missing_physics=False):
    if mesh.get('class') != 'MeshPart':
        raise ValueError('Runtime visual proxy expects a MeshPart')
    collide = bool_property(mesh, 'CanCollide')
    if expected_collide is not None and collide != expected_collide:
        raise ValueError(f'{name(mesh)}: Studio physics differs from registered No Collide')
    props = mesh.find('Properties')
    if props is None: raise ValueError(f'{name(mesh)}: missing properties')
    removed = set()
    for child in list(mesh):
        if child.tag == 'Item' and child.get('class') in RENDER_CHILDREN:
            for descendant in child.iter('Item'):
                removed.add(descendant.get('referent'))
            mesh.remove(child)
    mesh.set('class','Part')
    for prop in list(props):
        if prop.get('name') in MESH_PROPERTIES or prop.get('name') not in PART_PROPERTIES:
            props.remove(prop)
    transparency = next((p for p in props if p.get('name') == 'Transparency'), None)
    if transparency is None:
        transparency = ET.SubElement(props, 'float', name='Transparency')
    transparency.tag = 'float'
    transparency.text = '1'
    for key in ('CanCollide','CanTouch','CanQuery'):
        # Do not silently change physical/query behavior for a Location Asset.
        if fill_missing_physics and key != 'CanCollide' and not any(
                p.get('name') == key for p in props):
            ET.SubElement(props,'bool',name=key).text=str(collide).lower()
        bool_property(mesh,key)
    shadow = next((p for p in props if p.get('name') == 'CastShadow'), None)
    if shadow is not None:
        if shadow.tag != 'bool': raise ValueError(f'{name(mesh)}: invalid CastShadow')
        shadow.text = 'false'
    else:
        ET.SubElement(props,'bool',name='CastShadow').text='false'
    return removed
