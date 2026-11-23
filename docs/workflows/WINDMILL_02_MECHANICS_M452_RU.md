# M452 · Windmill 02 — Rotation + Door

## Asset boundary

`windmill_02` is a **Location Asset** (`Game1DecoAssetSlug=windmill_02`), not a House. The server uses `EnvironmentAssetService.Observe`, the existing indexed placement lifecycle. No new global Workspace server scans or separate player requests.

## Rotation

- In the final static FBX, `blades` and `fabric` are separate **unskinned MeshParts**; do not apply a new Armature Modifier to them.
- Their authored mesh centers/pivots stay in place. Client `WindmillRotorVisual` uses **fabric.CFrame (center of the wheel)** as the common rotating frame, applies the same world delta to the *initial* `blades.CFrame` and `fabric.CFrame` (no accumulating transforms).
- Default 360° / 3 seconds, `Options -> Rotations -> Windmill 02` (`rotations.windmill_02.enabled`, `secondsPerRevolution`). Generated `GameOptionsRegistry` is the runtime read-only source. It is updated through Asset Manager Save and Studio Sync.
- Spins along **fabric local Z** (normal to its rotor plane); test direction/axis in Studio Play on the published mesh. If FBX local axes differ, update the rotor axis contract, not manual Y/Z offsets.
- Visual only: `Bone.Transform` is not used for the rotor. Server retains static collision/anchoring; the client uses culling at 350 studs, a single render callback, global server time for synchronization. Rotating visuals must not be used as authoritative hit/collision geometry.

## Door

- `windmill_door_socket` is the **skinning Bone** (door hinge), and `windmill_door_handle_socket` is a **separate authored Attachment or Bone** for the interaction point. Both are required to create the interaction prompt; no guesses or procedural socket insertion.
- The supplied `windmill_02.fbx` had **no** `windmill_door_handle_socket`. Add it in source Blender, export/publish, and Sync explicitly to enable opening on existing Place models.
- F / touch ProximityPrompt, server distance <= 8 studs via `CharacterSpatialRoot`, cooldown, per-placement `Game1WindmillDoorOpen` and `Game1WindmillDoorChangedAt` attributes. These attributes replicate; **Bone.Transform does not replicate**.
- Each client evaluates `windmill_door_socket.Transform = CFrame.Angles(0, theta, 0)` (up to 90°) with 0.55s smoothstep. Door is a skinned MeshPart; skinning remains supported. If the FBX hinge local Y is not vertical, correct the source bone axes and test rather than silently translating geometry.
- On open, the authored door collision is disabled on the server; on close it is restored after 0.55s. No door physical animation/hitbox sweep; collision should be tested with players, streaming and closing while occupied.
- Session attributes only; MMO persistence, access rights, locking and anti-obstruction are follow-up mechanics. Static verification cannot certify Play behavior.

## M452 building migration

Run **once** after applying the patch:

`python system/control-center/migrations/m452_buildings_keep_two.py`

Retains `smithy_01` and `windmill_02`. Explicitly retires `weapon_shop`, `windmill_01`, `smithy` using `LocationAssetStore.delete`; generates an SQLite snapshot and asset archives before deletion. Regenerates Location Asset registry. No cloud asset deletion, no Workspace/Place mutations, FBX sources preserved. Re-running is idempotent. A new unknown building causes a fail-closed stop instead of accidental blanket deletion.
