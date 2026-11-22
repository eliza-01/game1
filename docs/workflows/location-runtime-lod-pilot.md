# Location Runtime visual pilot — local Studio verification

This is a **draft-only** first client FULL / LOD1 / UNLOADED implementation for
`stone_fence_02` (174 placements in Snapshot #133) and `stone_pillar_03`
(27). It does not change the source authoring Place and does not authorize publication.

## Ownership

- `place/game1_runtime_source.rbxlx` is a manually saved XML **authoring** Place.
- Runtime Builder first checks snapshot geometry and SHA256, produces a byte-identical
  `authoring_backup.rbxlx`, then writes a new `runtime_place.rbxlx` that retains
  each root Model and independent server collision Part but strips its visual MeshPart.
- The builder embeds a bounded `Game1LocationRuntimeManifest` StringValue into
  **ReplicatedStorage of the Runtime copy only**. Its compact JSON includes the
  exact authored visual MeshPart world CFrame/Size and Model Pivot for each placement.
  `placement_manifest.json` remains the full inspection sidecar.
- Server bootstrap `LocationLodTemplateService` recognizes the embedded marker,
  validates catalog and geometry contract, loads exactly four published Model
  templates (FULL and LOD1 per slug) with owned-model insertion, and stages only
  their single sanitized visual MeshParts in ReplicatedStorage. Load failure is
  reported; a template cache `Ready=false` means the draft is **not valid to publish**.
- Client `LocationWorldStreamer` validates the same manifest and clones its own
  camera-distance-dependent MeshParts locally. Only local visuals change. They
  are Anchored, CanCollide=false, CanQuery=false and CanTouch=false. Server-held
  collision Parts, LandscapePainter, Real Estate and unmanaged objects remain intact.
- Desired states reuse `LocationLodDistancePolicy.Resolve` (FULL <120 studs,
  LOD1 <280, UNLOADED beyond; hysteresis ±12 after initial selection).
  Maximum eight visual changes per 0.25 seconds, per client. This first pilot
  uses a bounded 4-template cache, **not** full sector streaming/prefetch.

## Studio test (do NOT publish)

1. Install patch; restart Control Center. Save a clean authoring Place as
   `place/game1_runtime_source.rbxlx` and run **Scan Place → Preflight → Prepare**.
   An earlier Runtime draft created *before this patch* lacks the marker:
   it must be rebuilt; do not edit it manually.
2. Confirm runtime report `publishAllowed=false`, generated manifest marker,
   backup SHA256 and counts. Preserve all original source and backup files.
3. Open a **copy** of the new `runtime_place.rbxlx` in Roblox Studio. Do not
   overwrite the editable original or publish it. Connect Rojo to current project.
4. Run Studio Play (prefer **Test → Server & Clients**, two clients). The
   Check visual FULL / LOD1 / UNLOADED transitions by moving the camera.
   The debug counters were retired in M434. Check Output for `[game1][LOD]` template load failures. If the
   cache fails, halt; do not silently accept disappearing visuals.
5. Approach and retreat from fences/pillars; verify their world orientation,
   physical size and textures match the authoring Place; confirm no extra
   collision and no client-owned geometry on the server. Test different cameras
   for two clients; then 10 load/unload cycles and a weak mobile device.
6. Report pivot offsets, sizes, shadow artifacts or visual mismatches with
   screenshot + Studio Output. FULL/LOD1 authored mesh pivots are **not assumed
   aligned** by this implementation; actual comparison in Studio is required.

## Explicit remaining blockers

- Runtime publishing remains **blocked**, even if Studio Play looks correct.
- Sector indexes, per-sector prefetch, cancellation of stale asset requests,
  mobile budgets and coverage of non-managed parts of Workspace are not complete.
- Studio XML export still cannot prove the editor has no unsaved changes.
- Four ReplicatedStorage prototypes are a bounded pilot, not final memory budget.
