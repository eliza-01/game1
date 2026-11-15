# game1 Place

The canonical authored Place is **`game1.rbxl`**.

For a brand-new project, generate the seed place with:

```powershell
.\place\build-place.ps1
```

The build command injects a temporary Baseplate + SpawnLocation only while
building the initial place. **Live Rojo does not own Workspace scene children.**
After opening/saving the place in Studio, positions and other authored Workspace
changes remain in the `.rbxl` instead of being reverted by Rojo sync.

`current.rbxl` is deliberately **not used** in game1. If a `place/current.rbxl`
appears here, verification fails because it may be a RobloxLineage Place copied
into the wrong project.

To intentionally regenerate a fresh seed Place:

```powershell
.\place\build-place.ps1 -Force
```

This overwrites the authored place, so use `-Force` only when that is actually
what you want.

## LOD Manager Runtime draft (not publish-ready)

`LOD Manager → Scan Place` must be performed in the current Studio Edit session.
Then explicitly save the **current** authoring Place via `File → Save to File`
as **Roblox XML Place** to `place/game1_runtime_source.rbxlx`. This is a
separate local export; check you have not switched the editing target in Studio.
The `.rbxl` authored Place remains canonical. Saving an older local copy cannot
include unsaved changes from Studio.

`Preflight saved Place` checks the selected Location Models against the exact
Scan snapshot, including per-MeshPart CFrame, Size and owned collision Part.
`Backup + Build Runtime draft` first creates and verifies a byte-identical XML
backup, then writes a separate `runtime_place.rbxlx`, immutable placement
manifest and build report under `.control-center/runtime-builds/runtime_*`.
The build only strips visual MeshParts of explicitly approved
`stone_fence_02` / `stone_pillar_03` instances. It leaves all protected
LandscapePainter, Packages, houses and other Location Assets untouched.

**DO NOT PUBLISH this draft.** A client FULL/LOD1 rendering runtime and
multi-client / mobile validation are separate future stages. The XML source
export and runtime builds are git-ignored and are never included in dumps.
