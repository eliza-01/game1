# M420 · Live sword cursor and combat-root stabilization

- **Client:** `AttackController` reuses Bow's per-render camera ray for melee through the *complete* authored attack animation. `AimPoseController` composes yaw/pitch at the upper-body bridge only; `MovementController` remains the sole writer of physical movement and moving leg-facing. Sword may yaw its upper bridge across the full cursor arc when moving. Bow keeps its original 100-degree moving pose envelope.
- **Network:** Camera aim is sent at most once every 0.10 seconds through existing `MeleeAimUpdate` until HitEnd, with the existing late capture. No damage/hitbox/weapon transform is accepted from the client; server ray validation and one authoritative HitEnd are unchanged.
- **Server:** `AttackSessionStore` updates attack facing with the latest validated pre-HitEnd aim. `MeleeMovingFacing.Resolve` uses that horizontal aim for both stationary and moving attacks, falling back to the physical root only if the sample is absent. Target arc, environment contact and landscape sway consume the same facing; range, occlusion, timing and damage are server-owned. This replaces M419's movement-speed/root-yaw clamp.
- **Monsters:** The existing `MonsterAttackLocomotionController` also observes `MonsterCombatActive`. During combat and near the camera it removes RootBone translation (including vertical) after animation evaluation, while retaining rotation and the lower-body attack-pursuit blend. The navigation Humanoid remains responsible for physical movement; no additional render loop or monster-name exception is introduced.

## Required Studio Play / mobile acceptance

1. Sword: W, A/D, diagonals, S/backpedal, Walk, stationary, jump, immediate reverse camera, repeated attacks, attack ending with camera opposite its starting direction. Confirm torso and arc track the reticle continuously; legs retain M419 travel/gait, and only one hit is dealt at HitEnd.
2. Bow: Draw, strafing, Release, post-Release tracking and single damage capture remain unchanged.
3. Monsters: Confirm `guard_02` no longer sinks by half a body when entering Aggro/Chase/Attack. Compare `HumanoidRootPart.Position.Y` to the visible RootBone Transform during the transition. The actual guard FBX and Studio simulation are not included in the diagnostic dump; root-motion cause remains to be verified in Play.

This patch must be installed on both client and server for sword impact alignment. No asset publication or data migration is required.
