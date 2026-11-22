# M433 · Ivy · Location Assets

- `services.location_asset_taxonomy` owns the new category `ivy` within **Flora**.
- The same ID is consumed by registration, editor, library filter, DecoManager and
  new managed placement folder `Workspace.Game1DecoAssets.Ivy`.
- On first `LocationAssetStore` startup, `location_asset_category_migration`
  upgrades **only** `ivy_02`, `ivy_03`, `ivy_05` whose current category is `bush`.
  It creates a timestamped SQLite backup before changing any rows, increments
  their authoring revision to invalidate stale editing sessions, and re-exports
  `LocationAssetRegistry.luau`. Repeated startup is a no-op.
- Published Model IDs, mesh ID history, atlas bindings, FBX hashes/paths,
  per-asset LOD, collisions and placements remain unchanged. Historical FBX
  paths may still contain `/bush/`; moving them would break source provenance.
- **No automatic Studio Place reparenting.** Existing ivy models under Bushes
  remain where the author positioned them; new placements use Ivy. Runtime and
  Studio Sync match by asset slug, not by category folder name.
- To roll back authoring identity, stop Control Center, preserve the current
  database and restore the M433 pre-migration SQLite backup after verifying
  no subsequent authoring edits were made. Re-export LocationAssetRegistry.
