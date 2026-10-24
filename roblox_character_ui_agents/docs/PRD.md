# Character interface · product requirements (draft)

## Goal

Start an original fantasy MMORPG character interface in Roblox. Draw inspiration from the **clarity, density and atmosphere** of classic PC MMORPG inventory interfaces, including Lineage, while maintaining original artwork and interaction patterns.

## Confirmed requirements

- Provide an **inventory window**.
- Within the inventory interface, the **equipped weapon area/slot must appear left of the inventory item slots/grid**.
- The experience should receive a custom visual treatment rather than relying entirely on stock Roblox UI styling; the exact appearance requires owner/vision approval.

## Recommended MVP sequence (proposed, not yet approved)

- A static but real Roblox `ScreenGui` inventory prototype with sample items, clear equipped-weapon region on the left, and an item grid on the right.
- Opening/closing, visual states and interaction only after their behavior is decided.
- Add real inventory/equipment game-state integration only after the visual foundation and data contract are approved.

## Explicitly undecided

Slot count/capacity; exact window dimensions and on-screen anchor; initial visibility; open/close key/button; movable window vs fixed; resizing; item categories and rarity; weapon icon and statistics; multiple weapon sets; drag/drop and click behavior; tooltips; equipped-state behavior; other equipment slots and character tabs; gamepad/mobile targets; other HUD panels; localization and accessibility requirements. See `QUESTIONS.md`.

## Not currently in scope

Server-side inventory persistence, combat stats, equipment validation or anti-cheat, monetization, trading, and new character interfaces. These are not rejected features; they are simply **not authorized for this slice**.

## Initial acceptance criteria

1. The real Roblox rendered inventory matches an **approved** visual design for the target viewport.
2. The equipped weapon region is visibly and structurally **to the left of** the inventory grid, without overlap.
3. Native GUI elements exist for the interactive structure; this is not a single flattened non-interactive image.
4. Any demonstrated sample item/data is synthetic and does not pretend to be persistent game state.
5. Screenshots and reported checks come from a real Roblox Studio Play/client session or are marked `not_run`/`blocked`.
6. Unresolved feature decisions remain open rather than being inferred from prototype visuals.

Owner approval is needed before treating proposed MVP behavior as fixed requirements.
