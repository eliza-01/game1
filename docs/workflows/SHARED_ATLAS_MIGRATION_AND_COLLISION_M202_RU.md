> **Историческая документация M202.** Механизм `LegacyAtlasMigration` заменён M203. Действующие контракты и инструкции — [ATLAS_INDEPENDENCE_M203_RU.md](ATLAS_INDEPENDENCE_M203_RU.md).

# M202 · Migration of retained and legacy shared atlases + collision defaults

## Purpose

M199 intentionally retained deleted owner identities (`estate:<slug>:<part>`, `location:<slug>`) to keep published Image Asset IDs resolvable. This accidentally prevented reusing those *model registration* slugs. M201 fixed displayed atlas names, not historical owner links. M202 migrates the data, not just the message.

## Data flow

1. On Control Center / Host Agent startup, `RealEstateStore` calls `LegacyAtlasMigration.migrate()` **after** both stores have initialized. All currently published legacy owner-based links in Real Estate and Location Assets are candidates; existing M199 `retained_shared_textures` are mandatory migration targets.
2. Preflight resolves each reference through existing store semantics. It verifies a numeric published Image Asset ID, original PNG/JPG/WebP path within project, file SHA-256 and published SHA-256 (if present), and image dimensions. Unpublished *active* links are left unchanged; an invalid *retained* link cannot silently migrate or unblock a slug.
3. Prior to writing, the service creates **two SQLite backups**, one of `.control-center/game1.db` and one of `.control-center/game1_real_estate.db`, in `.control-center/backups/before_m202_atlas_migration_*`.
4. Before reusing a deleted slug, texture bytes formerly stored under that model's mutable directory are copied to a **content-addressed immutable `assets/source/texture-atlases/<key>/<size>/migrated/<sha>/` location** and the copied checksum is verified. Existing independent Atlas Registry sources are already immutable and are reused without copying. Neither original nor uploaded files are deleted. The archive copy is an additive file operation; on transaction rollback an unused copy can safely remain.
5. Both SQLite files are updated using a **single attached SQLite transaction**. Published identities are adopted as `texture_atlas_variants` or matched to existing variants only when the **source hash and Image Asset ID both match**. A family key/resolution conflict never overwrites a different published ID; the historical variant gets a distinct internal key.
6. Surviving `location_assets.texture_reference_slug` and `real_estate.textures_json[*].reuseReference` are cleared **only after** a direct `texture_atlas_bindings` row is allocated (or an existing binding is verified). The authoritative Image Asset ID remains unchanged. Registry/Studio exports are regenerated, with no cloud calls.
7. Old `retained_shared_textures` records are removed once their consumers have detached and the published image is stored independently. A historical `retained_atlas_migration_audit` row keeps the retired origin solely for audit, not for resolving future atlas bindings. Obsolete retired-owner bindings are deleted, so the **same deleted house or location slug can be registered again**.
8. Re-running the migration is idempotent; no extra variants, bindings or Roblox uploads are created. New `preserve` deletions run the same detachment **before** deletion. Failed preflight leaves all registrations and links unchanged. `mode=all` still deletes its explicitly confirmed legacy dependency chain.

Migration does not touch FBX sources, Model Asset IDs, player/character recipes, atlas pixels, Roblox cloud assets, or their publication queues. Modern registry bindings are never remapped to a different image.

## Shared-asset deletion dialog

The modal still groups shared atlases by Image Asset ID and lists their users. After the migration, consumers of an independent atlas are informational only: deleting a former owner **must not cascade-delete** them. Cascade applies only to actual remaining legacy owner links.

## Collision defaults

- `door`, `window_frames_glass`, and collision mesh (`COL_`) start with **No Collide unchecked** (CanCollide enabled).
- Other visual meshes keep **No Collide checked** by default.
- `window_frames_glass` still has Glass on by default.
- Existing explicit saved per-part settings always take precedence. No database rewrite of collision options is performed.

## Validation / recovery

Run the project unit tests and verify after installation. Check `.control-center/backups/` for the pre-migration SQLite backup pair. Reopen the Control Center and check the prior deleted slug can be registered, while Image Asset IDs on other houses/location objects are unchanged. If a source was removed, the console includes `[game1][atlas migration]` and preserves the owner link; restore the exact original texture from project backup, then restart to retry. Do not delete `retained_shared_textures` manually to unblock a slug.

**Known unrelated baseline:** the uploaded diagnostic project lacks an authoritative timeline for `human_male__weapon__hands__attack__01`; its 3 verify regressions are pre-existing and not changed by M202.
