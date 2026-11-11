# M282 · Landscape Painter: Surface Branches (v1)

## Ownership / scope

`system/landscape-plugin` is a **separate** Roblox Studio Edit-mode plugin. It builds
`generated/Game1LandscapePainter.rbxmx` and installs
`%LOCALAPPDATA%/Roblox/Plugins/Game1LandscapePainter.rbxmx`. This installation
**must not** touch `Game1Bridge.rbxmx`, DecoManager, Place Registry, published
Model/Mesh/Image IDs, or runtime scripts.

The plugin is a landscape authoring tool, not a gameplay system. v1 draws
procedural branches with cylinder Parts. Later vine/ivy/leaf and light tools
can share its input/session layer and consume the existing published Location
Asset catalog through the same Host Agent; they must **not** create a second
asset database. Asset browser/networking and lights are intentionally not in v1.

## Studio workflow

1. Open **game1 · landscape** toolbar > **LandscapePainter**.
2. In the dock choose **Начать · Ветка**. Move the cursor over a BasePart or
   Terrain; a colored 3D point preview appears. Adjust color (`#RRGGBB` or a
   swatch), diameter (0.04–4 studs), and surface following (0–4).
3. Click the first surface point; click subsequent points. Each successive
   pair commits a branch segment, and the next pair continues the line.
4. `Enter` or **Завершить** finishes the tool. `Esc` cancels the uncommitted
   endpoint and exits. Previously committed segments remain and can be undone.
5. Studio `Ctrl+Z` undoes the latest committed segment.

The UI sample reflects current color and thickness. The viewport previews
are temporary HandleAdornments under `CoreGui`; no Part is written into the
Place until the second click. Raycasts ignore authored landscape branches to
prevent accidental snapping to the generated stems instead of the wall.

## Surface following contract

- Level `0`: 1 straight cylinder, no projection.
- Level `1`: one midpoint projected on the surface, resulting in 2 segments.
- Level `n`: recursively `2^n` segments, at most `16` (level `4`).
- The surface normal on every clicked point defines the exterior side.
  Interior projection casts from that side **toward** the surface and accepts
  only normals oriented compatibly with interpolated endpoint normals
  (dot >= 0.25). Reverse-facing hit results are rejected; no automatic flip.
- When a sample has no admissible hit, it stays on the linear span and the UI
  reports `точек без прилегания`, rather than silently selecting a backside.
- Cylinder centerlines are offset by half their diameter along the selected
  outward normal to keep them visible at the surface.
- Input rays and projection queries exclude `Game1LandscapeDecor`. No
  generated stem acts as a new snap surface. Maximum span 250 studs.

## Authored storage and revision semantics

```
Workspace
  Game1LandscapeDecor (Folder)
    Branches (Folder)
      Branch_<unique> (Model)
        Stem_01 (Part)
        Stem_02 (Part) ...
```

Each Model carries `SchemaVersion=1`, `AuthoringTool`, `StrokeId`,
`SegmentIndex`, `Thickness`, `ColorHex`, `SurfaceFollowLevel`,
`SnappedMidpoints`, `UnsnappedMidpoints` and source point/normal Vector3
attributes. This is a versioned *authoring* payload for future brush editing,
not a new Asset Registry or an auto-published Roblox asset.

Generated cylinders are Anchored, noncolliding, CanQuery=false and do not
participate in hit detection or gameplay collision. `ChangeHistoryService`
wraps each committed segment as one undoable action, and failures cancel
without modifying the Place. Settings are stored in plugin-local settings.

## Validation boundary

Static tests verify module manifest consistency, independent installation,
metadata contract and editor behavior guards. A real Roblox Studio Edit-mode
smoke test is still required to verify cursor raycasts, CoreGui adornments,
Undo/Redo, normal-projection on irregular geometry, `Enter` behavior and
correct persistence through Place save/reload.
