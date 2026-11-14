# M343C · Location Assets: Collision Blueprint → Place / Place Registry Sync

**Scope:** Location Assets only. No Real Estate, no `col_mesh`, no Blender Pivot edits, no authored Explorer folders. Base revision: M343D (after M343B1A).

## User flow

1. Collision Capture is unchanged: select the verified Model and arbitrary authoring Parts anywhere in Workspace, then Capture.
2. New DecoManager **Place** reads the CURRENT Blueprint revision and creates transparent physical Parts in the placed Model automatically.
3. Existing placements are updated through **Location Assets → Place Registry → Scan → Sync**. A model with current Mesh/Texture but missing collision is shown as **Collision ✕ требует Sync**, including for material-only assets without Atlas ID.
4. Repeat Scan after Sync; **Collision ✓ актуальна** means that the correct revision, part count, ID, size, transform and physics properties are present. Re-running an unchanged revision must not create duplicate Parts.
5. A later Capture changes the Blueprint digest; the next Place Registry scan again flags the old instances for Sync. Mesh Asset ID and atlas remain unchanged.

## Ownership / safety

- Saved canonical Blueprint lives in SQLite `location_asset_collision_blueprints` (same storage as M343A). Studio reads it from the existing authenticated `/api/location-assets` registry and Place Registry catalog; no separate migration or publication is required.
- Exactly the generated primitive `Part`/`WedgePart`/`CornerWedgePart` descendants tagged `Game1LocationCollisionOwned = true` belong to this sync mechanism. They are direct children of the placed root Model, not new authoring folders. No user-created authoring Parts are deleted.
- Each generated Part is `Anchored=true`, `CanCollide=true`, `Transparency=1`, `CastShadow=false`, and uses its captured `collisionGroup`, `canTouch`, shape/size and CFrame. For an actual physical collider Roblox effectively requires `CanQuery=true`, so it is forced true when CanCollide is true even if captured `canQuery=false`. See Roblox BasePart.CanQuery limitations.
- CFrame is computed from the existing placed Model pivot. Existing Pivot, PivotOffset, PrimaryPart, Mesh/Texture/Material/Color, placement identity, original FBX and sources are not edited. `Model:GetScale()` applies to relative position and size of the generated primitive without moving the pivot. Dynamic/moving collision rigs are out of scope.
- Place Registry's explicit Undo recording covers updates to already placed instances. A Stage/Commit/Rollback operation prepares new Parts before replacing the previous generated set, and marks revision/hash only after successful commit. The generator is an optional protected `require` to avoid disabling unrelated Plots toolbar on failure.
- Pure read-only Scan never creates Parts. No automatic Studio startup migration. A placement with missing or ambiguous Model provenance/ID cannot be bulk-modified.
- Geometry rig Sync explicitly excludes generated collision Parts from immutable FBX rig replacement; current Mesh provenance still checks published Mesh IDs, not collision Parts.
- A changed Collision Blueprint changes the Place Registry digest and invalidates a prior Scan token. Refresh the registry before a new placement.

## Checks

- `test_location_collision_sync_m343c.py`: real temporary SQLite capture→registry→catalog propagation and digest changes, Studio source contracts, selection/Sync flags and report validation.
- `test_location_collision_blueprint_m343.py`, `test_location_collision_studio_m343b.py`, `test_location_material_registration_m343d.py`, Place Registry tests, Plots tests, `validate_luau.py` and main `verify.py`.
- **NOT RUN:** actual Roblox Studio Studio Edit/Play and game-client physics. Test one `stone_fence_02` in two positions and rotations, rescanning after Sync, repeated Sync, Undo, new Place, and then Save Place. Check exact collision group behavior. Do not assume a passed source validator is a Luau parser.
