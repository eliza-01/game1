"""Non-destructive skinning policy for a hinge-driven rigid Estate door.

The door is moved in Roblox as a Model (PivotTo); its hinge bone is a pivot
marker. A publication staging pass must not redistribute this rigid mesh's
weights onto handle/padlock sockets merely for bone-survival anchoring.
"""

HINGE = 'door_01_hinge_socket'


def check_rigid_hinge(vertex_weights: list[dict], available_bones: set[str]) -> dict:
    if HINGE not in available_bones:
        raise ValueError('door is missing hinge for rigid-hinge skin check')
    if not vertex_weights:
        raise ValueError('door has no vertices')
    for index, groups in enumerate(vertex_weights):
        hinge = groups.get(HINGE, 0)
        others = {name: amount for name, amount in groups.items()
                  if name != HINGE and amount > 1e-6}
        if abs(hinge - 1.0) > 1e-4 or others:
            raise ValueError(
                f'door vertex {index} must have weight 1.0 only on {HINGE}; '
                f'other influences: {sorted(others)}'
            )
    return {'status': 'rigid_hinge_preserved', 'preservedBones': len(available_bones),
            'protectedVertexCount': len(vertex_weights), 'modifiedVertexCount': 0,
            'weightPolicy': 'original_1_0_hinge', 'socketWeightInjection': False}
