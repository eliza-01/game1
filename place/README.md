# game1 Place

The canonical Place for this project is **`game1.rbxl`**.

It is generated from the clean Rojo project:

```powershell
.\place\build-place.ps1
```

`current.rbxl` is deliberately **not used** in game1. If a `place/current.rbxl` appears here, verification fails because it may be a RobloxLineage Place copied into the wrong project.

To intentionally regenerate an existing clean Place:

```powershell
.\place\build-place.ps1 -Force
```

The Studio-only `TrainingDummyService` creates a temporary attack target during Play tests, so the built Place does not need authored gameplay content.
