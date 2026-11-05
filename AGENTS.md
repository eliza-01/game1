# Engineering rules — all game1 code

**Scope:** These rules apply to every language and surface in this repository: Luau (server/client/shared), Python, JavaScript, SQL, PowerShell, Studio plugins, generated manifests and test/support tooling. They are not specific to Roblox Studio. This document is the in-repository source of truth for future changes. Treat these rules as review criteria, not an excuse for an unsafe wholesale rewrite.

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

## Current documentation and remaining decomposition (updated 2026-11-02)

M189 separates Character and Monster/NPC Animation Python store responsibilities without changing public contracts; see `docs/workflows/CHARACTER_ANIMATION_STORES_R3_M189_RU.md`. R3 is not finished. The M83 audit is **historical**. M85–M105 implemented the bootstrap, Host Agent, Monster AI/Spawner, Hitbox/Combat and Studio Bridge extraction steps. Do **not** repeat their original "not yet implemented" work. The live documents are:

- [`docs/README.md`](docs/README Read First!.md) — documentation index, current vs historical.
- [`docs/spec/CURRENT_PROJECT_SPEC_RU.md`](docs/spec/CURRENT_PROJECT_SPEC_RU.md) — current product/technical contracts.
- [`docs/architecture/CURRENT_ARCHITECTURE_RU.md`](docs/architecture/CURRENT_ARCHITECTURE_RU.md) — module ownership and boundaries.
- [`docs/architecture/REFACTOR_ROADMAP_RU.md`](docs/architecture/REFACTOR_ROADMAP_RU.md) — still-pending refactor steps, acceptance and non-goals.
- [`docs/workflows/DEVELOPMENT_AND_VALIDATION_RU.md`](docs/workflows/DEVELOPMENT_AND_VALIDATION_RU.md) — test and handoff procedure.

Historical reports in `docs/history/` are snapshots, not normative contracts. Maintain the historical M83 audit at its existing path because a regression test pins that file. These rules remain binding; a newer document cannot silently waive them.

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
