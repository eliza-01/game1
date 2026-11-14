"""M347: target-pivot alignment, safe ID repairs, and Studio undo invariants.

Pure transform mathematics are tested without Roblox; Studio behavior still
requires manual acceptance with Game1Bridge installed in Edit Mode.
"""
from __future__ import annotations

from math import cos, sin, isclose
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
LUA = ROOT / 'system/studio-plugin/modules/StudioLocationInstanceReplace.luau'
JS = ROOT / 'system/control-center/static/location-instance-manager.js'
BRIDGE = ROOT / 'system/control-center/services/studio_location_instance_bridge.py'


def rotation(yaw, pitch, roll):
    # 3D rotation around Y, then X, then Z
    y = ((cos(yaw),0,sin(yaw)),(0,1,0),(-sin(yaw),0,cos(yaw)))
    x = ((1,0,0),(0,cos(pitch),-sin(pitch)),(0,sin(pitch),cos(pitch)))
    z = ((cos(roll),-sin(roll),0),(sin(roll),cos(roll),0),(0,0,1))
    return mul3(mul3(y,x),z)


def mul3(a,b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3))
                 for j in range(3)) for i in range(3))


def frame(pos,rot): return (pos,rot)


def compose(a,b):
    p,r=a; q,s=b
    return frame(tuple(p[i]+sum(r[i][k]*q[k] for k in range(3)) for i in range(3)),mul3(r,s))


def inverse(f):
    p,r=f
    t=tuple(tuple(r[j][i] for j in range(3)) for i in range(3))
    return frame(tuple(-sum(t[i][k]*p[k] for k in range(3)) for i in range(3)),t)


class LocationInstanceReplaceM347(unittest.TestCase):
    def test_target_mesh_anchor_exactly_replaces_old_model_pivot_for_3d_rotations(self):
        # This is the CFrame composition used by positionAtSource(); the model
        # and mesh anchors intentionally differ in both position and rotation.
        source=frame((143.0, 18.0, -51.0),rotation(.81,-.27,1.3))
        target_model=frame((9.0,-22.0,11.0),rotation(-.7,.41,.22))
        target_mesh=compose(target_model,frame((7.0,2.0,-9.0),rotation(.66,.32,-.25)))
        next_model=compose(compose(source,inverse(target_mesh)),target_model)
        relocated_mesh=compose(compose(next_model,inverse(target_model)),target_mesh)
        for x,y in zip(relocated_mesh[0],source[0]):
            self.assertTrue(isclose(x,y,abs_tol=1e-9),(x,y))
        for r1,r2 in zip(relocated_mesh[1],source[1]):
            for x,y in zip(r1,r2): self.assertTrue(isclose(x,y,abs_tol=1e-9))
        self.assertNotEqual(next_model,source)  # selected mesh != target Model pivot

    def test_new_published_mesh_is_available_but_source_mesh_is_not_a_choice(self):
        code=LUA.read_text(encoding='utf8')
        self.assertIn('local options = {{id="model", label="Pivot новой Model"}}',code)
        self.assertIn('ipairs(meshAnchors(target))',code)
        self.assertIn('return anchorOptions(template)',code)
        self.assertIn('sourceFrame * originalAnchorFrame:Inverse() * originalModelFrame',code)
        self.assertIn('positionAtSource(clone,old.geometry.frame,anchorId,approved)',code)
        self.assertNotIn('anchorOptions(states)',code)
        self.assertNotIn('local function sourceAnchor(',code)

    def test_source_transform_is_never_repositioned_and_undo_is_parent_based(self):
        code=LUA.read_text(encoding='utf8')
        commit=code[code.index('local recording = config.ChangeHistoryService:TryBeginRecording('):]
        self.assertIn('pair.before.root.Parent = nil',commit)
        self.assertIn('pair.after.Parent = pair.before.parent',commit)
        self.assertNotIn('pair.before.root:Destroy()',commit)
        self.assertNotIn('pair.before.root:PivotTo(',code)
        self.assertNotIn('pair.before.root:ScaleTo(',code)
        self.assertIn('Enum.FinishRecordingOperation.Commit',commit)
        self.assertIn('Enum.FinishRecordingOperation.Cancel',commit)
        self.assertIn('clone:ScaleTo(old.scale)',code)
        self.assertIn('Legacy.ResizeTarget(clone,old.geometry)',code)
        self.assertIn('math.abs(clone:GetScale()-old.scale)',code)

    def test_duplicate_ids_are_detected_and_reassigned_only_in_approved_scope(self):
        code=LUA.read_text(encoding='utf8')
        preview=code[code.index('if command.phase == "preview" then'):code.index('if command.phase ~= "replace"')]
        self.assertIn('assignPlacementIds(states,counts,config.HttpService)',preview)
        self.assertIn('newPlacementId=state.newIdentity',preview)
        self.assertIn('reassignedIds=rekeyed',preview)
        self.assertNotIn('Duplicated Placement ID in Workspace; repair first',code)
        self.assertIn('if state.idCount ~= 1 then',code)
        self.assertIn('and not counts[fresh] and not reserved[fresh]',code)
        self.assertIn('freshModel(template,targetRow,state,state.newIdentity',code)
        self.assertIn('Placement IDs changed since Preview; preview again',code)
        self.assertIn('newPlacementId',JS.read_text(encoding='utf8'))
        self.assertIn("type(value.get('reassignedIds')) is not int",BRIDGE.read_text(encoding='utf8'))

    def test_protocol_v4_prevents_stale_game1bridge_from_using_old_semantics(self):
        for path in (LUA, BRIDGE, ROOT/'system/studio-plugin/Game1Bridge.server.luau',
                     ROOT/'system/studio-plugin/install.ps1'):
            contents=path.read_text(encoding='utf8')
            self.assertIn('location-instance-replace-v4',contents,str(path))
            self.assertNotIn('location-instance-replace-v2',contents,str(path))
        self.assertIn('schemaVersion ~= 4',LUA.read_text(encoding='utf8'))
        self.assertIn('schemaVersion=4',BRIDGE.read_text(encoding='utf8'))


if __name__ == '__main__': unittest.main()
