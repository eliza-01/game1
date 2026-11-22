"""M441: mounted House props follow the established character spawn and rigid grip contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def src(path):
    return (ROOT / path).read_text(encoding='utf-8')


class FireplaceSocketHeadOrientationM441(unittest.TestCase):
    def test_existing_bone_facing_contract_is_the_only_heading_source(self):
        facing = src('src/shared/world/SocketFacing.luau')
        spawn = src('src/shared/world/HouseSpawnOrientation.luau')
        mount = src('src/server/world/HouseSocketAssetMount.luau')
        self.assertIn('return if fromBone then -frame.UpVector else frame.LookVector', facing)
        self.assertIn('SocketFacing.Forward(socketFrame, fromBone)', spawn)
        self.assertIn('SpawnOrientation.Upright(socketFrame, fromBone, 0)', mount)
        self.assertNotIn('SocketFacing.FullFrame(socketFrame, fromBone)', mount)
        self.assertIn('if not targetFrame then', mount)

    def test_fireplace_head_uses_identical_rigid_mount_as_weapons_and_hair(self):
        rigid = src('src/shared/rig/BoneModelMount.luau')
        mount = src('src/server/world/HouseSocketAssetMount.luau')
        self.assertIn('function BoneModelMount.Place(model: Model, grip: Attachment, socketFrame: CFrame)', rigid)
        self.assertIn('BoneModelMount.CreateGrip(reference,', mount)
        self.assertIn('BoneModelMount.Place(model, grip, targetFrame)', mount)
        self.assertIn('actual.Position - targetFrame.Position', mount)
        self.assertIn('actual.LookVector:Dot(targetFrame.LookVector)', mount)
        self.assertIn('actual.UpVector:Dot(Vector3.yAxis)', mount)
        self.assertNotIn('GetBoundingBox', mount)
        self.assertNotIn('CFrame.new(0,', mount)

    def test_character_clearance_is_not_copied_to_props(self):
        elevator = src('src/server/world/HouseElevatorService.luau')
        debug_spawn = src('src/server/world/HouseSocketService.luau')
        mount = src('src/server/world/HouseSocketAssetMount.luau')
        self.assertIn('Orientation.Upright(', elevator)
        self.assertIn('target:IsA("Bone"), 3)', elevator)
        self.assertIn('SpawnOrientation.Upright(getFrame(socket), socket:IsA("Bone"), 3)', debug_spawn)
        self.assertIn('SpawnOrientation.Upright(socketFrame, fromBone, 0)', mount)

    def test_docs_mark_asset_geometry_offset_as_separate_from_socket_heading(self):
        doc = src('docs/workflows/FIREPLACE_SOCKET_MOUNT_M441_RU.md')
        self.assertIn('Tail → Head', doc)
        self.assertIn('MeshPart', doc)
        self.assertIn('rig_carrier', doc)
        self.assertIn('clearance=0', doc)


if __name__ == '__main__':
    unittest.main()
