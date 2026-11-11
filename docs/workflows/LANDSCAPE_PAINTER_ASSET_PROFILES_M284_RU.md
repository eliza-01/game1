# M284 · Landscape Painter: published assets, pivot profiles and tether

## Scope

The Studio Edit-mode `Game1LandscapePainter.rbxmx` remains **independent** of
`Game1Bridge.rbxmx` and DecoManager's toolbar, selection, sync and replacement
commands. It reads the **same** `/api/location-assets` endpoint from the local
Host Agent and reuses the published-model preparation module
`DecoAssetLoader` and its exact dependencies **by source alias**, not a copy.
Its own `plugin.project.json` links the shared Luau source into the separate
plugin binary. No second registry, new publication, or automatic Place sync.

## Interaction

- **01 · Ветка**: unchanged M282 point-to-point strokes; follow 0–4,
  color and diameter; Enter exits; Ctrl+Z rolls back each segment.
- **02 · Ассет**: click `Обновить каталог`, search and select a published Location
  Asset, then `Начать · Размещение ассета` to show surface reticle and translucent
  3D preview. Click to commit a separate copy at its pivot; further clicks
  place additional copies. Enter/Esc stops the placement tool.
- The source Mesh/Atlas/Model IDs are not mutated. Skinned assets go through
  existing canonical carrier and texture processing in the reused loader.
- The **surface outward normal** defines the asset's facing (the asset's local
  **-Z** points outward). Local `yaw/pitch/roll` are applied afterward. This is
  independent of camera facing; ceilings, walls and slopes are supported.
  Authored object pivot/origin must represent its intended attachment point.
- The optional **tether** starts at the raycast surface point and extends along
  its outward normal by a configured length (default 2 studs). Its end is the
  asset pivot. Thickness defaults to 0.02 studs, independently configurable
  down to 0.02. Color is an arbitrary `#RRGGBB` hex value. It uses exactly the
  same `BranchGeometry.Apply` cylinder primitive as the branch tool.
  On ceilings this means hanging downward if the surface normal is downward.
  This is a rigid non-colliding authoring segment, **not rope physics**.

## Profiles

- `Save profile` creates a named preset with rotation and tether parameters in
  Studio **plugin settings**. Max 60 profiles; no DB duplicates.
- `Use` toggles one active preset, used for **every new** asset placement.
  With Use off, the live controls apply.
- `Apply` uses the **selected profile**, regardless of Use state, to modify the
  **one selected Model** in Workspace under one Studio Undo recording.
- For a Game1LandscapePainter-authored Model, saved point/normal are the stable
  frame: repeated Apply is idempotent, can modify/remove the tether, and never
  changes the published Model Asset ID or shifts the surface anchor.
- For an arbitrary Model, Apply changes orientation in the world frame while
  preserving position. A tether cannot be constructed without a recorded
  surface anchor, so tether-enabled Apply is rejected **before** mutation.

## Output & scene safety

```
Workspace
  Game1LandscapeDecor (Folder)
    Branches (Folder)             # existing M282 branch strokes
    Assets (Folder)               # new authoring placements
      <slug>_<unique> (Model)
        <published model geometry>
        LandscapeAttachmentLine (Part; only when tether is enabled)
```

An authored asset stores `LandscapeSchemaVersion`, `LandscapeAuthoringTool`,
`LandscapeAssetSlug`, `LandscapeModelAssetId`, `LandscapeSurfacePoint`,
`LandscapeSurfaceNormal` and the applied orientation/tether parameters as
Attributes. All committed mutations use ChangeHistoryService recording for
Studio Undo. Failed asset loads leave the previous selection untouched.

The 3D ghost is under `Workspace.CurrentCamera`, `Archivable=false`, anchored,
non-queryable, and is destroyed on Stop/Unload. The cursor/cord overlay is a
CoreGui HandleAdornment. Generated `Game1LandscapeDecor` and the camera are
excluded from surface raycasts. Preview is not published or recorded in Undo.

## Boundaries and test requirements

The catalog requires the local Host Agent and Roblox Studio HTTP access. If
it is offline, the branch tool remains independently available. This is an
Edit-only tool: **no Studio Play**. A real Edit-mode smoke test should cover
published static and skinned Models; walls and underside of roofs; multiple
copies; angle/Use/Apply; transient preview, Undo/Redo and Place reload.
The installer builds only `Game1LandscapePainter.rbxmx` and does not overwrite
`Game1Bridge.rbxmx`.
