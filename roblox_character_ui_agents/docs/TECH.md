# Character UI · technical guidance (draft)

## Platform

Roblox Studio, Roblox GUI instances, Luau. Current experience/repository structure and runtime versions are **unknown** until inspected. Verify API details against current Roblox Creator Hub documentation and Studio behavior.

## Proposed separation of responsibilities

The following are architectural responsibilities, **not mandates to create files/frameworks with these names**:

- `InventoryWindow` / `InventoryGrid` / `EquipmentWeaponSlot` / `ItemSlot`: view-only GUI components.
- `InventoryController`: window state, input and binding between UI and an inventory-state interface.
- `InventoryViewModel` or adapter: transforms synthetic/approved item state into presentational values; later can consume a validated game inventory interface.
- `Theme`: reusable fonts, spacing, colors, assets and shared components.
- External inventory/equipment domain service: source of game truth, not owned by the UI. When real equipment actions are introduced, the server must validate them.

Keep related UI code cohesive; split only where it improves ownership and reuse. Reuse existing project services/components if present; do not duplicate them.

## Build and source strategy

- Prefer existing repository/Studio synchronization conventions.
- For a fresh project, consider Rojo + GitHub for Luau/source-managed instances. Document how GUI templates, Figma image exports and Roblox asset IDs are represented, imported and versioned. Do not assume that a `.rbxl` or Studio-only edit is captured by Git.
- Figma is not runtime. Approved exports become Roblox image assets; the GUI structure and behavior live in Roblox.
- Use `ImageLabel`/`ImageButton`, `UIGridLayout`/`UIListLayout`, suitable aspect and size constraints and 9-slice `ScaleType.Slice` where justified. Choose Scale/Offset per layout instead of enforcing a blanket rule.

## Validation

- Compare Figma and Roblox **Play-mode** at the agreed reference viewport. Capture the actual client screenshot and the Studio hierarchy for inspectability.
- Test placement of weapon region left of grid, row/column consistency, overflow/clipping, image clarity, text legibility, hover/click if implemented, and absence of unintended UI layering.
- Confirm only the platform/input targets that the owner has explicitly approved; list untested targets.
- Report code checks, build, Play test and manual comparisons separately as `pass`, `fail`, `not_run`, or `blocked`.
- Code checks/CI supplement, but do not replace, real GUI testing.

## External references

- Roblox UI 9-slice: https://create.roblox.com/docs/ui/9-slice
- Roblox UI sizing: https://create.roblox.com/docs/ui/size-modifiers
- Roblox position/size: https://create.roblox.com/docs/ui/position-and-size
- Roblox UI creation: https://create.roblox.com/docs/tutorials/use-case-tutorials/ui/interactive-ui
- Rojo project: https://github.com/rojo-rbx/rojo
