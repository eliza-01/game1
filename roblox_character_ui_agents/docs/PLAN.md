# Character UI · implementation plan (proposal)

Plan status: **DRAFT — owner/VISION approval required.** Do not create Linear tasks or make project writes until ownership and repository access are established.

## Slice 0 — inspect and decide

- Inspect existing Roblox place, `StarterGui`, Luau project, GitHub repo, Rojo/sync approach and Figma access.
- Identify exact target viewport(s), first open/close behavior and whether additional weapon equipment details are needed.
- Choose an art reference and agree on a Figma inventory frame. Record links.
- Create/update one Linear issue with visual references, acceptance criteria and exclusions.

## Slice 1 — visual inventory shell

- Build an original inventory design in Figma or agree on an equivalent image asset handoff.
- Implement a real Roblox UI structure: inventory panel with **left equipped-weapon region** and **right item grid**.
- Populate with labeled synthetic data; no game persistence or equipment logic.
- Capture Roblox Play screenshot and compare against the approved reference.
- Run REVIEWER pass; fix findings; seek VISION and owner acceptance.

## Slice 2 — approved interactions

Only after decisions: open/close behavior, selected slot, tooltip, click/drag or equip events, keybind/gamepad/touch as scoped. Continue small independently reviewable slices.

## Slice 3 — game integration

Only when approved: inventory state/service connection, server validation and production data. New gameplay behavior requires its own PRD/task.

## Completion and handoff

Use the process in `AGENTS.md`, including branch/PR evidence, independent review, owner merge permission and honest status reporting. No CI workflows are assumed to exist.
