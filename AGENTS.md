# Engineering rules — all game1 code

**Scope:** These rules apply to every language and surface in this repository: Luau (server/client/shared), Python, JavaScript, SQL, PowerShell, Studio plugins, generated manifests and test/support tooling. They are not specific to Roblox Studio. This document is the in-repository source of truth for future changes. Treat these rules as review criteria, not an excuse for an unsafe wholesale rewrite.

## Active project priority — Performance P0 (2026-11-27, M606a)

The owner has made completion of KBN-0035 through KBN-0039 the highest current project priority. Read `docs/README Read First!.md`, the Performance P0 sections of the current specification and architecture, and the [Kanban queue](docs/kanban/README.md) before changing code. Owner-approved exception M607: native equipment mounting (KBN-0037-T02) is first; then resume the remaining tasks in dependency order: profiler/baseline → spatial index → client → server → asset pipeline. All five cards are mandatory; the last card's P1 is only relative sequencing. Defer new mechanics and content expansion until all five cards meet their acceptance criteria; exceptions are blocking defects and work needed for acceptance. Keep prior cards and evidence intact.

Use small verified patches, shared infrastructure, measured before/after evidence, and explicit cleanup/budgets. Do not trade combat correctness, server authority, collision fidelity or visual correctness for unmeasured gains. CODE_COMPLETE is not DONE: record real Studio/DEV and physical mobile acceptance in Kanban; never turn static analysis into measured FPS/CPU claims. M605 is the pre-optimization baseline; M607 replaces rigid hair/weapon followers with native Bone RigidConstraint, no asset republish. M607 failed visual acceptance (jump equipment separation, NPC Idle sword offset). M608 failed visual acceptance too. M609 removes auxiliary Bones, restores pre-M607 authored socket frame and uses native joint on its animated parent, no follower. Owner confirmed M609 works in published Runtime and on a physical phone. KBN-0037-T02 implementation and owner functional acceptance are complete; the full regression matrix and quantitative CPU/Physics/frame-time comparison remain open under A02/T06. Current owner decision M613: defer new measurements and the full Profiler; refactor confirmed critical modules first (shared NPC/Monster sampler pool, then Spatial Index and critical consumers). M614: server combat uses shared NativePartSpatialIndex over existing queryable RootCollider parts; preserve exact narrow phase and no melee limit on headshot rays. Native query and performance acceptance remain open. M615: общий ActorAIScheduler для Monster/NPC с очередью deadlines; интервалы 0,1 с, Aggro 0,3 с и существующие боевые события сохранены. Experimental Navigation, Rescue Routes, BlockedWait и все таймеры не изменены. M616: локальный PlayerSpatialIndex (XZ, ячейка 32 studs, один ленивый снимок на пакет scheduler; порядок GetPlayers и точные policy сохранены). 1200 сравнений с полным обходом в Lua-модели; NPC остаются retaliation-only. M617: opt-in Adaptive AI LOD (Options → AI Performance): активные 0,1 с; агрессивный Idle сохраняет дедлайн Aggro 0,3 с, пассивный Idle и закреплённый NPC дома — контроль 0,3–2 с, событийное пробуждение до 0,1 с. Глубокий сон агрессивных отложен до гарантированного обнаружения входа в Aggro без потери реакции; навигация и боевые решения неизменны. Далее ComputeAsync budget (Legacy/NPC); Studio/DEV и замеры открыты. Keep measurement/acceptance tasks open. Capture M609 as the current baseline for subsequent changes; reproduce M605 separately for equipment A/B, without reverting the live DEV build.

## Domain boundaries and ownership

1. **One clear responsibility per module.** A service coordinates a use case, not rendering + persistence + networking + validation + simulation in a single implementation. Split by responsibility, not arbitrary line count. A module exposes a small named public interface; its internal data and helper functions remain private.
2. **Depend inward.** Shared contracts and deterministic algorithms must not depend on server implementations, client UI or tooling. Server owns authoritative simulation, combat validation, progression, persistence and spawning. Client owns presentation, local input and visual interpolation. Editor/plugin/Host Agent own authoring; they must not become gameplay dependencies.
3. **Reuse through contracts, not copies.** Common actor navigation, facing, collision, hit validation, animation choice and equipment attachment belong in deliberately shared modules. Character / Monster / NPC adapters specify different policies and lifecycles. Avoid `if name == 'warsmith'`-style special cases and don't reuse a monster store's vocabulary as a public NPC API.
4. **Separate policy, orchestration and mechanisms.** Configuration describes *what* (weapon type, state, speed). A resolver picks policy. A mechanic executes. A presentation module renders. Avoid mixing all four.
5. **Explicit ownership of runtime state.** For each actor, declare which service is the sole writer of each state/attribute. Use intentional state transitions, not inferred timers that compete with AI or animation tracks. Subscriptions, tasks, connections, temporary instances and spawned NPCs must have cleanup ownership and be safe under respawn/reinit.
6. **Stable, versioned contracts.** Every HTTP endpoint, RemoteEvent/RemoteFunction payload, Studio Bridge command and registry schema has documented identity, validation, schema version, error semantics and compatibility policy. Prefer thin transport adapters → application services → repositories. A handler must not directly own unrelated domains.
7. **One source of truth for data.** Use explicit migrations for SQLite and generated manifests; maintain backward compatibility or an idempotent upgrade path. Preserve identity and published IDs unless the user intentionally changes them. Generated content must be reproducible and must not silently overwrite editor-owned data. No secrets, media or heavyweight assets in diagnostics.
8. **Security and failure isolation.** Validate all untrusted input, particularly client-supplied combat data and Host Agent/Studio commands. Restrict debug mutations to Studio. Use least privilege, bounded work and timeouts. An optional debug service or single NPC should not prevent unrelated server services from starting. No arbitrary filesystem reads from web paths.
9. **Performance at MMORPG scale.** Avoid per-actor full-Workspace scans, unnecessary per-frame remote messages, creation of new tracks or physics constraints in tight loops, and unbounded registries. Define caches, memory/network budgets and cleanup. Explicitly distinguish server simulation rate from client render interpolation.
10. **Code review quality bar.** Descriptive names, strict Luau types where possible, pure helpers for calculations, narrow constructor inputs/dependency injection for testing, short cohesive files, no dead workarounds or hidden fallback behavior. Document intentional compatibility exceptions with ownership and removal plan.

## Required change workflow

1. Read current sources and contracts, identify the minimal responsible modules, and define observable acceptance criteria *before* touching runtime.
2. Separate behavior-preserving extraction from behavior changes. Never rewrite combat movement, animation and storage in one step without isolation tests.
3. Add or update focused unit and contract tests. Include real behavior/transition cases where possible; source-string assertions alone are insufficient. Test all affected entity types and the published game versus Studio-only mode.
4. For data changes, write reversible/idempotent migrations, create backup, test upgrade on a copy of actual manifests/SQLite data, and show rollback or recovery procedures.
5. Run `python system/verify/verify.py` and `python -W error::ResourceWarning -m unittest discover -s system/verify -p 'test_*.py' -q`, plus language/tool-specific checks. For movement/physics/animation/network changes, do a Roblox Studio Play regression; static tests cannot validate these.
6. Verify `git apply --check` against the actual supplied project version. Deliver changes as a patch from the game1 project root with one single PowerShell block; restart **only** services affected. Do not restart Rojo or open new consoles by default.
7. In every handoff describe boundaries changed, migrations, observed tests, untested runtime scenarios and any regressions/risks. Never claim full Studio validation from static tests.

## Current documentation and remaining decomposition (M189 baseline; M541 gameplay review 2026-11-26)

- Current gameplay source baseline: M541 (`game1_diag_2026-11-26_19-42-21.zip` + M541 patch); documentation-only M542 does not bump RuntimeVersion. See [`M541 Hub / World GP`](docs/workflows/M541_HUB_WORLD_PROGRESSION_RU.md) and [Design KBN-0031](docs/kanban/specs/KBN-0031.md).
- GP rewards are transient and restricted to owned ordinary zone kills in Studio. Never route them to account persistence; Guided/Group/Skilled must remain reward-free. Keep `CharacterProgressionView` shared rather than duplicate progression formulae. Hub ×3 is a temporary location policy, not a permanent stat. No class lock; release goals in Design are proposals, not published content.

M189 separates Character and Monster/NPC Animation Python store responsibilities without changing public contracts; see `docs/workflows/CHARACTER_ANIMATION_STORES_R3_M189_RU.md`. R3 is not finished. The M83 audit is **historical**. M85–M105 implemented the bootstrap, Host Agent, Monster AI/Spawner, Hitbox/Combat and Studio Bridge extraction steps. Do **not** repeat their original "not yet implemented" work. The live documents are:

- [`docs/README Read First!.md`](docs/README Read First!.md) — documentation index, current vs historical.
- [`docs/kanban/STATUS_2026-11-22_M439.md`](docs/kanban/STATUS_2026-11-22_M439.md) — current Kanban code evidence and unverified Studio/mobile acceptance for all 17 cards.
- [`docs/spec/CURRENT_PROJECT_SPEC_RU.md`](docs/spec/CURRENT_PROJECT_SPEC_RU.md) — current product/technical contracts.
- [`docs/architecture/CURRENT_ARCHITECTURE_RU.md`](docs/architecture/CURRENT_ARCHITECTURE_RU.md) — module ownership and boundaries.
- [`docs/architecture/REFACTOR_ROADMAP_RU.md`](docs/architecture/REFACTOR_ROADMAP_RU.md) — still-pending refactor steps, acceptance and non-goals.
- [`docs/workflows/DEVELOPMENT_AND_VALIDATION_RU.md`](docs/workflows/DEVELOPMENT_AND_VALIDATION_RU.md) — test and handoff procedure.

Kanban specs and cards must retain matching SHA256/revision/history; `verify.py` now checks this read-only via `KanbanStore` (M439). Historical reports in `docs/history/` are snapshots, not normative contracts. Maintain the historical M83 audit at its existing path because a regression test pins that file. These rules remain binding; a newer document cannot silently waive them.

## M203 · Real Estate / Location Atlas independence

Model slug cannot own or reserve atlas identity. New authoring calls `AtlasRegistry.adopt_file/bind/ensure_published`; old owner references and retained texture snapshots migrate into independent variants on startup; see `docs/workflows/ATLAS_INDEPENDENCE_M203_RU.md`. This does not migrate unrelated Weapon/Monster/NPC texture slot stores; they remain a separate architectural debt and must not be represented as compliant.

## M208 · plot × house placement authoring

`real_estate/placement.py` owns persisted `(plotIndex, houseSlug)` CFrame/scale bindings; Studio reads the selected Model and existing Plots catalog through `StudioHousePlacementCapture.luau`. This is not the gameplay purchase/spawn service. See `docs/workflows/REAL_ESTATE_PLOT_HOUSE_PLACEMENT_M208_RU.md`.

## M213 · native atlas formats

`AtlasRegistry.adopt_file` validates Pillow's actual source format; WebP even with
`.png` suffix is staged as a real PNG, and PNG/JPEG suffixes in storage match
actual bytes. Unsupported or unreadable images still fail closed. See
`docs/workflows/REAL_ESTATE_ATLAS_NATIVE_FORMAT_M213_RU.md`.

## M216 · Critical Location Assets Studio Sync safety contract

A Studio Sync MUST target exactly one explicitly selected Location Asset slug.
Never replace/destroy/re-parent a placed Model or MeshPart. No PivotTo, ScaleTo,
ApplyMesh or changes to CFrame/Size/physics/bones. The published Model Asset ID
is reference metadata, NOT the writable MeshPart.MeshId. Atlas Sync may only
update MeshPart.TextureID and existing SurfaceAppearance.ColorMap. Always
record changes to per-placement and Host Agent ID histories; all publications
of shared atlases require per-consumer explicit Sync. Reject legacy global
Studio Bridge commands. See docs/workflows/LOCATION_ASSETS_SAFE_ID_SYNC_M216_RU.md.

## M218 · Read-only Database / Asset History

The Asset Manager Database → Asset History view consumes the existing M217 audit through `GET /api/asset-replacements`; it never mutates Studio, asset IDs or authoring DBs. Display independent shared atlas publications as variant identities, not as belonging to an arbitrary model. Studio model_reference changes are metadata, not geometry replacements. See `docs/workflows/ASSET_HISTORY_DATABASE_M218_RU.md`.

## M219 · Location Assets row-scoped Studio Sync UX

Each Location Asset library row owns `Edit` (shared modal shell, original authoring form) and `Sync Studio` (explicit slug argument). Switching atlas variants must not silently invoke Studio Sync. `studio-sync.js` is the shared client dispatcher for Location Assets and Real Estate; backend and Studio operations remain domain-specific and must keep M216 non-destructive rules. See `docs/workflows/LOCATION_ASSETS_ROW_SYNC_EDITOR_M219_RU.md`.

## M220 · Location Assets resource workflow (supersedes M219 editor)

Location Asset registration is create-only, `Edit` is a dedicated resource workflow
with separate `Identity`, `Model · FBX`, and `Texture · atlas` operations.
Real Estate and Location Assets share editor tab/step presentation and common
Atlas Registry transport, not duplicated authoring pipelines. Publishing FBX
creates a NEW Roblox Model Asset ID and preserves the previous publication
in the append-only audit. Shared atlas republish never silently Syncs its
consumers. Studio Sync remains strictly scoped and non-destructive under M216;
updating reference metadata DOES NOT update an existing MeshPart's geometry.
See `docs/workflows/LOCATION_ASSETS_RESOURCE_WORKFLOW_M220_RU.md`.

## M221 · Explicit in-place FBX sync supersedes ONLY M216 ApplyMesh ban

Under an explicitly slug-scoped schemaVersion 4 Studio Sync, a guarded, shared
`StudioMeshInPlaceSync` may call `ApplyMesh` **on existing MeshParts** after full
matching/local-frame preflight and creation of rollback snapshots. Never clone,
replace, re-parent, delete, PivotTo or ScaleTo a placed Model. Preserve each
MeshPart's CFrame and Size, model identity, links and place structure. A changed
FBX has unavoidable collision-geometry implications; skinned/wrapped or
incompatible parts MUST fail closed. Audit actual `model` changes, not just
reference IDs; no mutation outside the requested slug. Old M216/M220 plugin
commands are incompatible with schema 4. Studio verification on a backup Place
remains mandatory. See docs/workflows/LOCATION_ASSETS_INPLACE_GEOMETRY_SYNC_M221_RU.md.

## M222 · One Studio rig replacement mechanism for Estate and Location Assets

`StudioManagedRigSwap` is the single staged managed-child-rig replacement
transaction for BOTH Real Estate placed-visual sync and Location Assets FBX
sync. Domain adapters select roots, published rig contents, authored anchors and
metadata; the common module stages, commits and rolls back child-rig changes.
Never destroy/replace or move a placed *root* Model. Real Estate continues to
anchor at its `house` MeshPart; Location uses a unique published MeshPart
authoring pivot. Preserve skinned Bones/Wrap hierarchy by copying the whole rig
from the published Model, rather than `ApplyMesh` into an existing skinned part.
M221's `StudioMeshInPlaceSync` is REMOVED; its manual skinned-mesh rejection
and `ApplyMesh` path are superseded. Sync stays explicit and slug-scoped, with
full audit and conservative preflight before any Place mutations. M216 remains
the historical safety floor concerning root identity, placement scope and audit,
not a ban on the now-shared managed CHILD rig replacement. See
`docs/workflows/SHARED_PLACED_RIG_SYNC_M222_RU.md`.

## M223 · Central Atlas retirement / authored plot previews

`AtlasRegistry.retire_variant` is the sole writer of atlas retirement and binding
migrations; never physically delete retained images, published IDs or publication
history, never auto-select a different atlas key and never trigger implicit Studio
Sync after a retirement. All consumers must be rebound in a single transaction
and their revisions incremented. SQLite is authoritative when MySQL audit is offline.

Real Estate Plot Place/Clear operates ONLY on separately marked authored
previews in `Workspace.Plots/NN/Houses`. The saved Placement binding is the
sole source of coordinates, and plugin changes must participate in Studio Undo.
No gameplay purchases, no mutation of unmanaged Workspace models or templates.
Read `docs/workflows/ASSET_MANAGER_ATLAS_PLOT_PREVIEW_M223_RU.md` before changes.

## M224 · Placement anchoring and Atlas Library UI

`RealEstatePlacementStore` owns the persistent per-binding anchored flag, with an additive
SQLite migration and unchanged CFrame capture schema. Studio mutates only marked
authored previews (`Game1PlotHousePreview`), never arbitrary Workspace contents.
Anchor/Free must use the authenticated scoped placement bridge and Studio Undo.
Re-Place may replace managed previews on the same plot but never unmanaged objects.
Atlas Delete means active-registry retirement with source/ID/history preserved,
not deletion of files or published Roblox assets. See
`docs/workflows/ASSET_MANAGER_M224_PLACEMENT_ATLAS_HOTFIX_RU.md`.

## M227 · Bulk authored house previews

`Place all` uses one selected house slug and ONLY saved Real Estate bindings from the server; it must never accept browser-supplied positions. `Clear all` is intentionally global across managed authored previews and never touches unmanaged Place objects. Single Place/Clear and bulk Place/Clear must share Studio preflight, staged clone/anchor verification, managed-only replacement and one Undo recording per command. Do not implement bulk by running individual commands 50 times. See `docs/workflows/REAL_ESTATE_BULK_PLOT_PREVIEW_M227_RU.md`.

## M228 · In-range reticle melee target independent of weapon contact

`AttackDamageResolver` merges the first in-range server hitbox under the validated
center-screen reticle ray with all authored weapon-volume contacts. Range gates
ONLY the reticle hit (using the actual contact point from `RootCollider`); the
physical sword segment and existing radius extension remain unchanged. A shared
attack session `hitTargets` prevents duplicate damage, and `headshotTarget`
limits headshot to one explicitly aimed head per attack. `AttackAimGeometry`
owns the pure radius test; client poses, HitStart/HitEnd and bounce precedence
remain unchanged. See `docs/workflows/COMBAT_RETICLE_PRIMARY_MELEE_M228_RU.md`.

## M230 · Legacy Plot Placement compatibility

M229's author `house` pivot is mandatory for **new capture** but must not
invalidate old M208 plot-local CFrames. Preview accepts legacy rows with absent
`houseAnchorLocalCFrame` through the original Model-pivot semantics while
reusing `StudioRealEstateHouseFrame.Align`; calibrated rows retain exact house
pivot alignment. Never synthesize or persist an assumed historical anchor.
M230 Studio preview protocol v4 is mandatory. See
`docs/workflows/REAL_ESTATE_PLACEMENT_LEGACY_COMPAT_M230_RU.md`.

## M231 · Location FBX collider / glass / skeleton inspection

`fbx_mesh_inspection.py` is the shared Blender bone reader.
`services.mesh_authoring_policy` is the shared name-role classifier.
`src/shared/world/MeshPhysicsCore` (Studio alias `StudioMeshPhysicsCore`) is the single MeshPart property writer for Estate and Location.
Estate M207 Precise for collidable remains unchanged; Location COL_* uses Box.
Location registration via Asset Manager requests inspection; older registrations
can be inspected explicitly without republishing. Reports are SHA-bound.
Never auto-Sync all placed instances on analysis, and never move their roots.
See docs/workflows/LOCATION_ASSETS_FBX_COLLISION_SKELETON_M231_RU.md.

## M232 · Single FBX authoring contract (supersedes M231 collider Box)

Shared `fbx_blender_report`, `fbx_mesh_inspection`, `mesh_authoring_policy`,
`mesh-authoring.js` and `MeshPhysicsCore` are the ONLY general inspection and
MeshPart physics mechanisms. Both Real Estate and Location Assets invoke these
with domain-specific identities and publication rules. **CanCollide=true always
means PreciseConvexDecomposition**, including Location COL_ meshes. Box is the
default only for No Collide. Selected FBX must be analyzed and its editable
mesh/bone controls shown BEFORE Register/Save. Location per-mesh options are
SQLite-backed, exported to Runtime, and applied by scoped Studio Sync protocol
6; legacy records stay unchanged until edited, except the erroneous collider
fidelity. See docs/workflows/LOCATION_ASSETS_FBX_AUTHORING_M232_RU.md.

## M233 · Location Model publication must never carry textures

Location Assets `Republish Model` uses only the explicit `/publish-model` API and
shared `staged_model(texture_mode="geometry_only")`. Staging strips Blender
materials from the temporary FBX, exports without embedded/external bitmap
references, and fails closed unless the report proves no material slots remain.
Atlas Image IDs are published only through the independent Atlas Registry.
Other model consumers keep their existing texture policy; no implicit Studio Sync.
See `docs/workflows/LOCATION_ASSETS_MODEL_ONLY_PUBLICATION_M233_RU.md`.


## M234 · One shared Atlas editor and explicit Apply / Sync

Location Assets and Real Estate mesh editor MUST render their atlas bindings through
`static/asset-atlas-editor.js`, backed by one AtlasRegistry and a common read-only
preview/explicit publication flow (`services/atlas_source_review.py`). One active
consumer binding; several attached selectable variants. `attach`, `select`, and
`preview-source` NEVER upload or invoke Studio. Republish a shared atlas only after
old/new comparison and explicit consumer-impact approval. Location Model publication
is model-only. Both modals expose one bottom-level explicit scoped Studio Sync;
report the actual Bridge error inline. See
`docs/workflows/SHARED_ATLAS_EDITOR_APPLY_M234_RU.md`.

### M236 · Location Assets published-ID Studio sync
- Studio Sync performs read-only `Find Mesh IDs` (schema 7), then an explicit
  token-scoped `Replace Texture` / `Replace Mesh` / `Replace Texture + Mesh`
  based on actual differences. Never mutate Place during Find.
- Preserve separate immutable Model Asset ID and per-version MeshPart.MeshId
  inventories. Match older placed geometry by Mesh ID, not importer paths/names.
- Both domain adapters use StudioManagedRigSwap for managed-child replacement.
  Never recreate or move the placed root; abort on uncertain authored frame.
- See `docs/workflows/LOCATION_ASSETS_ID_HISTORY_TWO_PHASE_SYNC_M236_RU.md`.

## M237 · Per-MeshPart Location Studio Sync

The Location studio scan must compare managed visual MeshPart MeshId and
applicable TextureID / SurfaceAppearance.ColorMap against published IDs.
(M238 overrides this milestone's earlier collider-texture rule: COL is physics-only.)
Expose current published Model/Mesh/Atlas IDs, every managed part with separate
status, and external historic matches as non-selectable diagnostics. Studio
Sync accepts only explicit pending-part selections from the one-time scan token.
Texture-only selections mutate selected parts; any geometry selection invokes
shared StudioManagedRigSwap for its entire managed child rig (never the root).
Partial sync must not acknowledge the whole Atlas Registry binding.
See docs/workflows/LOCATION_ASSETS_MESHPART_REPORT_SELECTIVE_SYNC_M237_RU.md.

## M238 · Studio selection, physics-only atlas and authoring defaults

Studio Bridge protocol 8 adds read-only `select` (scanToken + partKey),
selecting one scanned Model in Studio. `Find` never changes Studio Selection.
Location collision MeshParts (`COL_*`, `_col`, `col_mesh`) have no atlas
contract: report no Texture status or stale warning and never assign a new
Atlas ID to them. Shared FBX/Real Estate/Location authoring defaults
`DoubleSided=false`, while explicitly saved true/false remains authoritative.
External historical Mesh ID matches are selectable in Studio Explorer but
remain ineligible for Sync until linked to the registered asset through
a separately authenticated, explicit `attach` authoring operation; never infer ownership from
one matching ID. All modal rerenders preserve scroll position.

## M239 · Model-grouped Location Studio diagnostics

Show Studio scan results grouped by placed root Model, not separate COL/visual
sync cards. COL is physics-only: render just collider presence (or a concise
missing-COL warning), never Texture IDs. Each managed Model has one scoped
Sync; Sync All always renders and is a no-op if all managed models are current.
There is no UI Sync selection state. `Select in Studio` selects a Model;
`Select All` selects all scanned Models (including historic unlinked references)
with one read-only Studio Bridge phase `select` (schema 9, `partKeys`). Selection
never modifies the Place or marks an atlas synchronized; external historic
matches are never eligible for Replace without explicit verified linking.
Registered Assets uses persisted current-version published `visualNames` and
Mesh IDs; it must not infer Mesh IDs from FBX part names or list COL IDs.
See `docs/workflows/LOCATION_ASSETS_MODEL_GROUPED_SYNC_M239_RU.md`.

## M243 · Location ownership parity and per-group Sync

Location Find and `DecoPlacedAssetSync` MUST share `StudioLocationPlacementOwner`: never
use a separate nested-Model exclusion policy at Sync time. A marked ancestor
may not claim the parts of a nearer differently marked placement; reject
geometry changes that would overwrite nested independent rigs. Place Registry
`Sync group` uses the existing authenticated, journaled Location-only Sync
operation with the normal explicit backup confirmation; Real Estate edit/sync
is unaffected. See docs/workflows/LOCATION_PLACE_REGISTRY_GROUP_SYNC_AND_OWNER_M243_RU.md.

## M244 · Location placement fidelity and stale ownership labels

Location Studio Find reports are retained across Sync; a consumed token is locked
and a new read-only Find is automatic after success or failure. When another
Find cannot run, the previous report is displayed but cannot authorize writes.
`StudioLocationPlacedGeometry` is the *single Location-only* policy shared by
scoped Location Sync and Place Registry Sync. For verified unrigged one-visual
publications preserve placed visual `CFrame`, `Size`, `PivotOffset` and map new
COL by the same per-axis transform; never silently drop manually customized
multipart/skinned geometry. The shared `StudioManagedRigSwap` remains unchanged.
A foreign `Game1DecoAssetSlug` attribute is not proof of a foreign owner: confirm
full historical Mesh ID inventory before blocking Repair. Explicit Repair must
correct stale published Model ID/SHA metadata. See
`docs/workflows/LOCATION_SYNC_PLACEMENT_STATE_M244_RU.md`.

## M252 · Location publication reconciliation and additive COL repair

Location Place Registry MUST compare the complete published MeshPart multiset,
not merely a visual MeshId: two immutable Model publications may reuse the
visual ID while adding COL. `StudioLocationPublishedGeometry` owns this read-only
policy; copied `Game1DecoPublishedModelAssetId` is trusted only after matching
its entire historical inventory. Location `Repair` may add a unique independent
COL to an anchored, verified same-visual mesh without replacing existing Bone,
Fire or other authored children, and MUST disable legacy visual collision while
preserving transforms and undo. Unknown joints or ambiguous provenance fail
closed. `Repair` does NOT apply Surface Material/Alpha; those are explicit Sync
operations. No-op and blocked operations must report truthful change counts.
See `docs/workflows/LOCATION_PLACE_REGISTRY_RECONCILIATION_M252_RU.md`.

## M255 · Imported RootPart normalization for Location Assets only

`StudioLocationImportRoot` is the sole guarded converter of Roblox FBX-imported
invisible RootPart rigs to visual MeshPart-owned Bones and explicit rigid COL
welds. New Location templates are normalized by `DecoAssetLoader` before
placement. Existing placed rigs require explicit, journaled Place Registry
Repair and are blocked from Sync until then. Preserve Bone rest/posed world
frames, all MeshPart CFrame/Size and Model pivot; reject unknown external
joints, multiple visual rigs and removal of the only physical collider.
Real Estate/Character assembly and immutable Open Cloud assets are unaffected.
See `docs/workflows/LOCATION_IMPORTED_ROOTLESS_M255_RU.md`.

## M265 · Shared Character / Location skinned MeshPart connection

Character and Studio Location must use the SAME `src/shared/rig/SkinnedMeshConnection.luau` source. The Studio plugin maps it directly from `src/shared` (no duplicated implementation). After canonical published Location rig validation and detached importer RootPart normalization, link only disconnected visual/COL MeshParts to the authored `rig_carrier`. Preserve valid importer Motor6D/Weld paths and never add a cycle or duplicate joint. This assembly completion is performed only on fresh, unplaced model clones; it never repairs existing Place geometry, changes source weights/Bones, touches Atlas/Model IDs, or creates synthetic carriers. See `docs/workflows/LOCATION_SKIN_CONNECTION_M265_RU.md`. Roblox Studio skin/physics smoke verification remains mandatory.

## M264 · Location placement float-tolerant verification

Location legacy rig alignment verifies post-`ScaleTo`/`PivotTo` CFrame and pivot
with the same bounded tolerance as `StudioManagedRigSwap` (0.025 studs and axis
dot 0.9999), never exact floating-point equality. Size tolerance remains 0.025.
The staged transaction still fails before commit on any material transform drift.
See `docs/workflows/LOCATION_PLACEMENT_FLOAT_TOLERANCE_M264_RU.md`.

## M263 · Roblox importer Motor6D assembly in canonical Location rigs

Roblox may add an inert `RootPart` and internal `Motor6D` joints while importing
a multipart skinned FBX. This alone is not legacy authoring evidence. On a
fresh detached `LoadAssetAsync` clone only, `StudioLocationPublishedRigNormalize`
may remove one verified inert importer RootPart, move its original root Bones
to the authored `rig_carrier`, and remove only verified joints to that root,
while proving Model pivot, MeshPart transforms and Bone world/pose frames did
not change. `StudioLocationRigCarrier` may retain a Motor6D only when both
endpoints are distinct manifest MeshParts inside the same skinned v2 Model;
static assets, unknown children/joints, external/missing endpoints, duplicate
pairs and cyclic assemblies fail closed. M262 then migrates the normalized
published child rig through `StudioManagedRigSwap`; placed legacy roots are
never normalized in situ. See
`docs/workflows/LOCATION_IMPORTER_MOTOR_ASSEMBLY_M263_RU.md`.

## M262 · Historical Location rig migration by immutable publication

Retained Location slug aliases are the same placement identity for scoped Find
and Sync. A legacy visual + COL publication must be grouped by its verified root
Model/Placement ID, not rendered as separate assets per MeshPart. With a
canonical current publication, explicit Sync may replace the complete verified
historical managed child rig through `StudioManagedRigSwap`; it must load the
new immutable Roblox Model rather than synthesize parts or use `ApplyMesh`.
Preserve the placed root Instance, parent, pivot, scale, Placement ID and visual
placement transform; migrate slug/Model metadata only on commit and roll it back
with geometry on failure. Unknown or edited historical hierarchies fail closed.
See `docs/workflows/LOCATION_LEGACY_RIG_PUBLICATION_MIGRATION_M262_RU.md`.

## M256 · Location rig carrier v2 (migration in progress)

The M255 single-visual Bone-owner fallback is superseded by the real FBX-authored `rig_carrier` contract. For Location assets, never synthesize carrier MeshParts in Studio or silently mutate imported `RootPart`; use the separate, explicit, transactional Place Registry carrier migration only with proven published manifests and visual/collider transforms. This is **not a completed catalog migration** until all source FBXs have been republished and Studio tests pass. See `docs/workflows/LOCATION_RIG_CARRIER_M256_RU.md`.

## M257 · Canonical FBX publication, no skeleton Repair

Legacy imported `RootPart` and missing/invalid `rig_carrier` are **FBX publication** issues. Never move Bones or install a carrier via Place Registry Repair. Reauthor and republish the Model FBX with real Blender-authored carrier; preserve existing atlas Image ID and immutable Model history. Place Registry Find/Scan show the publication requirement and disable structural Repair. Existing placements are not silently mutated; Studio Sync remains independently guarded. See `docs/workflows/LOCATION_RIG_CARRIER_M256_RU.md`.

## M260 · One Blender rig_carrier authoring mechanism

Character and skinned Location FBX must call `system/asset-manager/blender_rig_carrier.py`.
Never duplicate carrier geometry/weights by domain, synthesize one in Studio, or
require carrier for static Location assets. Blender entrypoints must explicitly
import shared modules independent of working directory. Publication failures
must remain visible and must not publish Atlas or modify placed instances.
See `docs/workflows/LOCATION_CARRIER_BLENDER_SHARED_M260_RU.md`.

## M280 · One authored Bone socket facing contract, solid face colors

Every **directional** Blender Bone socket uses Tail -> Head as its facing
axis: imported `-BoneFrame.UpVector`. An ordinary Attachment uses `LookVector`.
All such transforms belong to `src/shared/world/SocketFacing.luau`, with
`HouseSpawnOrientation.Upright` responsible only for avatar world-up projection.
Do not copy raw Bone CFrame onto front-facing items or add per-asset 90°
compensation. Hair builder/client share `FullFrame`, and compound extras remain
root-local. Static locator-only sockets (smoke, handles) are not forced into a
facing contract. See `docs/workflows/CHARACTER_BONE_SOCKET_AND_FACE_COLORS_M280_RU.md`.

Character Assembly eye/brow slots are **solid-color**, with `face_colors` per
side and no atlas picker/appearance. Shared CharacterColorBinder is the one
runtime tint mechanism also used by compound hair. Armor and head atlas
contracts remain unchanged. Never republish mesh/image assets just to tint.

M618: only Legacy Monster / NPC native path requests use NavigationScheduler; never enqueue Experimental Navigation or Rescue Graph. Preserve original combat ownership and deadlines. Queued results are consumed by the current navigator, never apply movement from a worker. See `docs/workflows/M618_NAVIGATION_BUDGET_RU.md`.


M619: Runtime LOD stage 1 only. StaticPlacementIndex is a conservative immutable BVH for Location snapshot pivot; never use it to decide LOD or change House bounds semantics. Keep previous desired/actual records until unload; preserve nil on first sample, logical UNLOADED for omitted records. Composite effects still run separately for late roots. Do not change server physics or AI. Continue with threshold queue. See `docs/workflows/RUNTIME_LOD_STREAMING_REFACTOR_SPEC_RU.md`.

M620: Runtime LOD stage 2. LodThresholdCache uses conservative clearance from the last resolve, not per-frame deltas. Keep queue reconciliation on stationary ticks for late prototypes/proxies; do not bypass fallback or actual ownership. LodTransitionQueue has one pending entry per placement; age after 8 ticks, unload-first, alternating house reservation for oversized aged entries. M621: shared LodPrototypeCache is keyed by Instance identity, generation, variant and FULL component contract; event-invalidated readiness states (missing/incomplete/ready/invalid), two bounded retry checks, late template-folder/Ready handling, cached immutable assembly metadata/bounds and atomic rebuild on replacement. Preserve fallback and local failedAssemblies semantics. Cache is shared with HouseVisualAdapter for LOD1 prototype readiness; House spatial/budget integration remains stage 5. Next: incremental assembly & work budget. Studio/DEV acceptance pending.

M622: Runtime Location stage 4 — `LodAssemblyJob` / `LodRuntimeWork`: detached incremental assembly (single mesh, multipart LOD, composite FULL); 12 build + 8 cleanup operation groups/frame, separate atomic commit reservation up to 132 groups, 16 queue checks/category/frame, one active job (≤64 visual meshes), at most two retired bundles. Commit revalidates proxy identity/current CFrames, preserves previous visual until swap and keeps effects tied to actual. Desired/prototype generation/root changes cancel staging; cleanup is incremental. Old Location cost clamp removed. House keeps independent 8/tick reservation pending stage 5; Studio Preview multipart drains the same job synchronously. Counts are not a hard CPU deadline; native streaming, effect traversal and Studio/DEV/Mobile profiling remain acceptance items. T03/A03 open.

M623: Real Estate stage 5 — every house part is a record in the common static BVH, threshold cache, aging transition queue and `LodRuntimeWork`. House influence uses a conservative sphere around scaled snapshot bounds; exact policy remains `ResolveHouse` with surface distance and per-part hide/LOD1. FULL acquisition (`HouseMeshRequests`) has four combined in-flight/ready slots, 15 s retry, generation and moving-proxy identity checks; async completion cannot publish. Detached result enters the common job, old actual survives until atomic commit, failure or absent preferred prototype preserves old actual; cold missing LOD1 can fall back to FULL. Missing unpublished part LOD1 retains FULL→UNLOADED. Shared unload/retirement handles committed geometry. Discard of a stale raw async MeshPart is immediate (bounded by four slots), outside the staged assembly counters. Only active moving parts are followed each frame; lost proxy detaches the owned mesh and removes DoorRaycast binding, stream-in rebinds using current CFrame and appearance. Static active parts refresh proxy color/material during local observation. Server physics, manifest, sockets and authority unchanged. Lua mocked lifecycle and mixed spatial/async oracles; actual Studio/DEV/Mobile, House5 interactions/two-client and profiling remain NOT_RUN. Preview still synchronous; T03/A03 open.

M624: opt-in Runtime LOD diagnostics (authorized Studio/DEV debug dock, PC/mobile), bounded capture with heartbeat/callback elapsed, queue/desired→actual latency, local candidates, sorts/cache/async/work counters, peaks and client memory at boundaries; no telemetry or new scheduler. Studio Preview teardown now disconnects Workspace subscriptions, restores authored visibility and destroys local folder. Authoring assembly remains synchronous; composite/tagged passes are measured, not eliminated. Actual Studio/DEV/PC/Mobile, two-client and A/B acceptance NOT_RUN; T03/A03/A06 remain open. See docs/workflows/M624_RUNTIME_LOD_ACCEPTANCE_RU.md.

M625: `LocationCompositeEffects` replaces the periodic global composite pass with shared manifest-path prefix subscriptions (`ChildAdded/Removed`) and scoped root `DescendantAdded/Removing`. Initial discovery once per resident root; actual LOD commit/native detach controls cached effects, not desired. Hidden authored Enabled state is restored on show, stream-out and Stop; late descendants and replacement roots are handled. Compiled paths are static (runtime rename unsupported). Observable external Enabled=true while hidden is suppressed and retained; false writes indistinguishable from the local false cannot be observed without an authoritative separate state, so dynamic server-controlled effects are not newly opted in. No new Heartbeat/remotes/manifest changes; doors, rotors, House effects and tagged visual pass unchanged. Owner deferred incremental Studio Preview as optional tooling. Real Studio/DEV/physical Mobile and A/B acceptance remain NOT_RUN; T03/A03/A06 open.

M626 · Near-first Runtime LOD: после публикации M625 владелец подтвердил обычную работу без заметного ухудшения, но на слабом телефоне ближние ограждения догружались позже дальних домов. `LodLoadPriority` использует позицию HumanoidRootPart игрового персонажа (камера в меню/при отсутствии root), минимальную surface distance по authored bounds Location/House, кольца по 32 studs. Camera-based visibility/LOD thresholds и пространственный индекс не меняются. В общей очереди: unload отдельно, затем ближайшее кольцо, cold перед upgrade, aging только внутри класса и кольца. Ближайшее незавершённое кольцо ограничивает admission сборок даже при ещё отсутствующем template/proxy; 4 секунды без прогресса разрешают следующие кольца, поздний ассет остаётся приоритетным. При respawn/телепорте порядок обновляется без ожидания очередного 0,25 s sample; активная недопустимая сборка отменяется. Четыре async FULL slots и прежние бюджеты сохранены; при нехватке слотов для ближнего FULL разрешено освободить один готовый дальний detached result, не отменяя in-flight вызов. Без новых Heartbeat, массового PreloadAsync, remotes, изменений серверной физики, манифеста и Preview. Порядок управляет клиентской сборкой/публикацией и house FULL requests, а не гарантирует порядок native Roblox replication, CDN fetch или GPU render. Профилирование/стресс-тесты отложены по решению владельца; ближайшая практическая проверка — обычный вход в игру на слабом телефоне. T03/A03/A06 формально открыты.

## Next after M626 · MNPC Visual LOD (planned, not implemented)

Owner accepted M626 loading functionally; formal profiling/stress acceptance and incremental Studio Preview are deferred. Socket & Door Optimization is deferred until a new floor-aware interaction design. Next task KBN-0037-T08/A07: read `docs/workflows/MNPC_LOD_SPEC_RU.md`. Entity-first: one shared lifecycle/navigation shell/pose readiness/presentation/LOD infrastructure for BOTH Monster and NPC, designed together from M628; domain adapters preserve existing AI, spawn, equipment and interaction behavior. No duplicate NPC/Monster lifecycle, scheduler, LOD queue or cache; no dependency of either domain on the other. Both real spawn/AI entrypoints must use the shared lifecycle and pass common contract tests before M628 is complete. Build stable server entity/navigation shell before visual; AI registration must not require Animator or ready visual presentation. Activate native authoritative pose only on actual server-wide demand (all relevant players and combat consumers), keep existing OBB algorithms and gameplay. Client presentation is independent per observer. Hiding a replicated FULL rig does not prove no animation evaluation. Exactly FULL / LOD1 (one static mesh per visual variant, zero visual rig animation/sampler, follows root) / UNLOADED. Reuse shared LOD admission/cache/work budget; dynamic actors are not static BVH placements. Keep AI/combat/server authority, M609 and M626 behavior. No stress-test prerequisite for normal development; record NOT_RUN honestly. Installation blocks for runtime patches end with agreed background Rojo restart via sync.ps1 after Control Center.

M627: read `docs/workflows/M627_MNPC_POSE_PILOT_RU.md` before changing MNPC Runtime. Isolated Studio-only pose probe (ordinary active Monster/NPC, no benchmark) compares skinned reference vs plain Bone carrier and private native evaluation, optionally observes two clients. No bootstrap registration or live actor changes. Owner Studio logs received: plain carrier matches sampled Gremlin/Guard poses; private native carrier did not meaningfully animate; replicated NONE client still sees active bones/tracks. M628 starts opt-in entity-first lifecycle foundation; strict per-observer native isolation and combat readiness must be proven before enabling dormancy/strict LOD. T08/A07 remain open. No custom pose evaluator or hitbox redesign without separately demonstrated blocker and owner decision.

### Engineering judgment

Treat owner implementation suggestions as hypotheses, not commands to implement blindly. Reject technically unjustified approaches directly, explain trade-offs and choose the smallest effective design. Do not drift from the agreed task or invent adjacent optimizations; distinguish proven benefit from assumptions, and preserve current working contracts.

M628 step 1: read `docs/workflows/M628_MNPC_ENTITY_FOUNDATION_RU.md`. Both production spawners now create the entity via `actor/MnpcEntityLifecycle` before cloning a template, using `MnpcNavigationShell` and `MnpcVisualRig`; remove no further combat dependency until its readiness/cleanup contract is implemented. `NpcRigFactory` retired; `MonsterRigBuilder` only preserves Monster RootBone bridge. `Game1MnpcRigReady` gates existing FULL binding; not a claim of independent AI or zero skeletons. M628 remains open: AI registration without pose, shell-only movement, safe attach/detach and demand readiness next. Do not change existing hitbox algorithms. Studio/DEV NOT_RUN.

M629 (M628 step 2): read `docs/workflows/M629_MNPC_AI_POSE_BINDING_RU.md`. Both AI entrypoints register without a ready native presentation; shared `MnpcPoseBinding` tickets guard stale completion, NPC `NpcMotionIntent` records movement/return state independently, real attack/cast requires a committed native pose. Production still FULL; do not enable detach/dormancy until shell/collider metadata and combat demand/release safety are proven. Keep T08/A07 open.

M630 (M628 step 3): read `docs/workflows/M630_MNPC_SHELL_GEOMETRY_RU.md`. Shared `MnpcRigGeometry` caches immutable template geometry (Instance/revision); `MnpcEntityLifecycle.PrepareShell` and `MnpcNavigationShell.CreateQueryCollider` prepare inactive RootCollider without visual clone. `MnpcVisualRig.Attach` rebases on current root and reuses collider. Both production spawners use the contract but still attach FULL immediately. No guessed bounds, new loops, or combat math changes. Unsupported metadata keeps FULL path. NPC equipment-independent context, autonomous production shell and demand/release readiness remain open. Studio/A07 NOT_RUN.

M631 (M628 step 4): read `docs/workflows/M631_MNPC_PRESENTATION_LIFECYCLE_RU.md`. Shared `MnpcPresentationLifecycle` lease owns exact attached rig/wrapper children, weld, and successful NPC weapon mounts; release preserves prepared shell after domain consumers and OBB are quiesced. Both production spawners use lease on terminal disposal only. NPC equipment context resolves before clone; effective mounted context retains previous validation/fallback. Do not confuse geometry reacquire oracle with full live pose rebind or per-client isolation; production still FULL, A07 NOT_RUN.
