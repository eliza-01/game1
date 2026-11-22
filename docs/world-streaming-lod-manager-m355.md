# Eyesland · Location LOD Manager — configurable Runtime Build (M355)

> **Актуализация M439 · 22.11.2026:** первоначальная процедура M355 ниже описывает раннюю конфигурацию. В M427 общие custom LOD distances удалены: у каждого Location Asset свои `assetDistances`, у каждой части Real Estate свои пороги, общие — `hysteresis` и нативные Roblox Workspace properties. Studio Preview (M426/M429) синхронизирует Save с Play; Runtime Build использует отдельный проверенный manifest. [Актуальная схема и приёмка](kanban/STATUS_2026-11-22_M439.md).

## Single ownership

- Place Registry is the sole source of Studio placements and their independent collision evidence.
- `config/location_streaming.json` (schemaVersion=2) stores per-slug `assetDistances`, per-slug modes, shared hysteresis and Workspace profile. The server validates and atomically updates it through `POST /api/lod-manager/settings`. With no file, the conservative default selects only `stone_fence_02` and `stone_pillar_03`.
- Runtime Builder consumes the same settings and verified revision. Preflight token is invalidated when the selection/profile changes. Authoring XML never changes; a separate Runtime XML gets the Workspace properties and a schema-v2 immutable client placement marker.
- Published `LocationAssetRegistry` provides cloud model IDs; the client never submits asset IDs. Only selected FULL/LOD1/LOD2 prototypes are imported on the server. Clients create local noncolliding visuals. The Runtime publish gate remains **closed** until Studio and mobile verification.

## Per-asset mode

- **Off**: source visual stays in the Runtime copy (Roblox's own instance streaming may still unload it naturally).
- **FULL → Hide**: published FULL visual only, client unloads it beyond Hide.
- **FULL → LOD1 → Hide**: requires an actively published LOD1.
- **FULL → LOD1 → LOD2 → Hide**: requires actively published LOD1 and LOD2. The LOD2 publication workflow is not yet available; this mode is disabled until it is.

The initial authoring inventory supports static assets with exactly one visual MeshPart; optional `SurfaceAppearance`; zero collisions only if the MeshPart is both `CanCollide=false` and `CanQuery=false`; or 1–256 owned independent `Part` / `WedgePart` / `CornerWedgePart` collision pieces. Other rig, bone, weld, light, animation, or complex hierarchy instances must **remain unmanaged** until a separate contract exists. For every selected type, *all* its recognized placements must pass preflight. No per-placement silent skipping.

## Historical defaults of M355 (not shared runtime thresholds)

| Area | Setting | Value |
|---|---|---:|
| Client camera LOD | FULL → LOD1 | 120 studs |
| Client camera LOD | LOD1 → LOD2 | 260 studs |
| Client camera LOD | Hide / UNLOADED | 400 studs |
| Client camera LOD | Hysteresis | ±12 studs |
| Roblox Workspace | StreamingEnabled | true |
| Roblox Workspace | StreamingMinRadius | 64 studs |
| Roblox Workspace | StreamingTargetRadius | 1024 studs |
| Roblox Workspace | ModelStreamingBehavior | Improved |
| Roblox Workspace | StreamingIntegrityMode | PauseOutsideLoadedArea |
| Roblox Workspace | StreamOutBehavior | Opportunistic |

Roblox recommends the latter Workspace values in its instance streaming guidance. The client LOD values are project starter values, not Roblox defaults. `StreamingTargetRadius` is **not a strict visual draw distance**: Roblox may retain previously loaded instances beyond the radius. Roblox streaming is measured around the replication focus; custom LOD distances are measured from the camera.

## Procedure

1. Open the authoring Place; run a fresh **Scan Place**.
2. In **LOD readiness**, set a streaming mode for eligible assets or use **Enable all ready**. Other systems and unsupported geometries stay Off.
3. Adjust **each asset's** LOD1/LOD2/UNLOADED thresholds; only hysteresis and native Workspace properties are shared. Each (?) explains one control. **Default** fills values but does not save; click **Save settings**.
4. Save the original authoring Place as `place/game1_runtime_source.rbxlx` in Roblox XML Place format.
5. Run **Preflight**; check selected counts and source SHA256. Click **Backup + Build Runtime draft** (no typed confirmation). A red Save Place copy reminder remains visible; the build still creates and verifies its own byte-for-byte backup.
6. Open **only the new Runtime copy** in Studio, connect Rojo, test 2 clients with differing camera distances and check geometry, collision, and Output. Do not publish until validated.

The **Copy Studio Command Bar** action helps apply the *same Workspace* profile to the authoring Place; properties not available to Command Bar must be set manually in Studio Workspace Properties. Saving Control Center settings alone does not modify an open authoring Place.
