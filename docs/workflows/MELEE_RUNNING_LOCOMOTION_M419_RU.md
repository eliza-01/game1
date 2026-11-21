# M419 · Sword / Bow · Run + attack

> M420 supersedes the M419 **attack-facing** paragraph below. The M419 leg/travel policy remains current; see `SWORD_LIVE_CURSOR_MONSTER_ROOT_M420_RU.md`.

- During an attack, `MovementController` owns `ControllerManager.MovingDirection` and moving `FacingDirection`. For both bow and melee, feet face travel (or camera-forward for backwards movement); the shared spine bridge owns upper-body aiming. Moving attacks never write the physics root `CFrame`.
- The weapon policy still owns the attack speed modifier. Explicit Walk / backward movement is capped to walk speed, including during sword swings; running sword retains multiplier 1. `CharacterAnimationController` plays Walk/Run/combat_idle on the lower body according to actual movement, and the existing `AttackUpperBodyComposer` only overlays spine descendants.
- Moving melee is now a bounded server camera-oriented arc: the **initial normalized camera direction** is retained separately from optional late headshot updates. At the authoritative HitEnd, `MeleeMovingFacing.Resolve` clamps that direction to 100 degrees from the *server-observed physical root facing* only if horizontal velocity is at least 1.5 studs/s. Below threshold / invalid aim, the previous root-facing arc is used. Environment bounce, landscape sway, and target queries all receive the same facing. This changes only the arc's facing; distance, width, occlusion, hit timing and damage authority remain unchanged. No new remotes or client hitbox geometry.
- Bow release/hitscan remains unchanged. No Studio-only shortcut or asset-name special case.

## Device/Studio acceptance

In Studio Play with the sword and bow, check: attack during W/run; A/D sideways with camera turning; diagonal W+A/W+D; S and backpedal; walking with modifier; start walking during swing; stop and resume during swing; jump; repeat attacks; bounce; male/female if available; keyboard and mobile stick; single HitEnd contact in forward/sideways camera sector; collision bounce. Inspect `MovementState`, `AnimationAttackLowerBodySlot`, `AnimationAttackUpperBodyComposed`, `AnimationAttackCompositionError` and observed damage arc. There is no automated Studio runtime in the diagnostic environment.

This is an integration change and requires a new game runtime/deployment. Server and client must both receive M419. Do not ship only the client half.
