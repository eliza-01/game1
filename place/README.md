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
