# M387 · Real Estate Runtime authoring (contract, not runtime activation)

## Ownership and status

- `RealEstateStore` is authoritative for `house_levelN_variant`, its FULL mesh publications, independent per-MeshPart `distanceStreaming`/`loadDistanceStuds`, and appearance. These authoring settings were introduced before M387.
- `services.house_lod_resource` owns one independent, versioned, geometry-only House LOD1 Model Asset per stable house slug. It stages an FBX named `<house_slug>_lod1.fbx`, records an immutable revision history and keeps existing FULL meshes, collisions, sockets and Plot placements untouched.
- `services.house_runtime_profile` owns the per-type streaming intent (`off`, `full`, `lod1`) and the FULL→LOD1 / unloaded thresholds and hysteresis. These settings do **not** implement streaming by themselves.
- `LocationWorldStreamer` remains the single future client scheduler. Do not add per-house/per-mesh Heartbeat connections or poll Workspace from the Real Estate editor.
- M387 fixes `StudioTextureAppearance.ApplyVisual`: a material/color update in combined `Material + Atlas` can no longer skip the existing `ApplyDistance` call. Already placed homes must be explicitly synced in Studio to receive new distance metadata.

## Runtime compilation requirements (NOT part of M387)

1. Compile the authoring `.rbxlx` into a separate runtime draft without modifying the authoring Place or Plot bindings. Fail closed on missing publisher IDs, duplicated/ambiguous house instances or unsupported skeleton relationships.
2. Retain server-owned Plot, Collision Blueprint, socket interaction and door state. Remove only visual MeshParts owned by the runtime compiler; do not remove their canonical socket carrier or server scripts.
3. Produce an explicit versioned per-house manifest keyed by **stable house slug + stable Plot ID**, with author pivot, authored local transforms, published mesh/atlas IDs and per-mesh FULL visibility distances. Do not invent IDs from mesh names or bounding boxes.
4. In FULL mode, request the subset of visual parts whose ranges include the camera. When House LOD1 begins, ALL FULL visuals must be removed before the ONE House LOD1 model is shown. At unload distance remove the model. A client camera may cross thresholds during an async fetch; cancel or disregard stale results.
5. Reuse the one-second visual scheduler and existing load/unload operation budget. Perform immediate re-evaluation after first spawn/teleport. Never replicate all FULL templates eagerly to ReplicatedStorage and call that memory unloading.
6. Verify door/handle animation, colliders, sockets, interior floors, cold join, repeated threshold crossings, mobile load, and memory/graphics delta in Roblox Studio. A successful `verify.py` run does not verify these.

## House profiles

`off`: old authoring behavior. `full`: FULL visual→unloaded (LOD1 not required). `lod1`: FULL→one published House LOD1→unloaded. Distances use studs; thresholds must be positive and hysteresis must avoid overlap. In `lod1` mode no FULL MeshPart visibility distance may reach the House LOD1 threshold. LOD1 is invalidated when FULL FBX SHA changes until explicitly restaged/reviewed.

**Safety gate:** `runtimeReadiness.runtimeVerified` intentionally remains `false` until the Runtime compiler and Studio validation actually support houses. Do not use this authoring state as a DEV publication approval. The existing Location Assets Runtime builder remains independent and unmodified.
