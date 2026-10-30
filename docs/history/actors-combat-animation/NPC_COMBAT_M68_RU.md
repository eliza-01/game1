# M68 — NPC combat: monster-like, server authoritative

> **Исторический документ.** Фиксирует состояние на момент указанного этапа; отдельные механизмы могли быть заменены. Действующие контракты: [актуальное ТЗ](../../spec/CURRENT_PROJECT_SPEC_RU.md), [архитектура](../../architecture/CURRENT_ARCHITECTURE_RU.md).


## Architectural boundaries

- `NpcSpawnerService`: server population/respawn/death; creates actor and binds/unbinds AI.
- `NpcRigFactory`: original authored skeleton + movable `HumanoidRootPart` (same physical navigation height as monster) + inert `RootCollider`; welds only the visual root. Never edits bones.
- `NpcCombatAIService`: per-NPC behavior from `NpcRegistry`, target selection, cooldown, attack timeline and server hit verification. One scheduler for all NPCs; no weapon-volume contacts for NPC.
- `ActorCombatTargeting`: shared LOS, horizontal range and valid player-character queries; no actor-specific assets.
- `ActorChaseNavigator`: MoveTo with asynchronous path fallback; no attack or animation logic.
- `NpcAnimationService`: animation state machine for idle, combat_idle, run, attack, death. Owns the animation tracks, not physical navigation.
- `NpcEquipmentService` + existing `WeaponEquipService`, `WeaponAttachmentController`: equip both hands through existing Character socket contract. Weapon presentation has no effect on NPC attack range or damage.
- `WeaponPresentationState` + `NpcWeaponVisibilityController`: scoped `disarm=true` only while an idle_special runs. No death-disarm, no drop and no timestamp-based weapon detach in M68.

## Behavior contract

- `behavior.aggressive=false` means passive NPC. It still takes damage, dies, and respawns; it does not initiate attacks.
- When `aggressive=true`, `aggroRadiusStuds` and `attackRadiusStuds` must be positive. NPC scans for live player characters and pursues them using server-owned Humanoid.
- At range NPC plays its registered attack from active equipment animation subtype or `base`. If no attack animation exists, a timed attack is still possible (animation is not a spawn requirement). `AttackSpeed` determines fallback hit cadence and animation playback speed; a future NPC-specific AnimationSpeedScaling rule can override this.
- If a timeline exists for the selected `clipId`, its `Hit` event and duration control damage timing. Otherwise a configurable stat-based fallback is used. Hit validates distance, vertical tolerance, frontal arc, line of sight and life state on server at impact.
- All damage goes through `DamageService.Apply`; feedback through `HitEffectService.Publish`. No weapon volume, hitbox overlap or client-side attack requests for NPC.
- NPC loses target on invalid death or when target exceeds leash distance from original spawn. The current simplified model stops rather than navigating back to spawn.
- Death immediately invalidates pending delayed attacks and navigation. Weapon remains in hand throughout death presentation. No special weapon detach on a death frame yet.

## Production and compatibility

- Existing registered NPCs keep their values (they are currently passive with zero aggro/attack radius unless changed in Asset Manager).
- To activate an NPC: edit registration, enable Aggressive, set positive aggro/attack radius, save metadata, then restart Play after Rojo sync. Republish model/animations only if their actual content changed.
- Existing monsters' AI and Characters' melee/weapon volume paths are not changed by this patch.
- M65 special-idle crossfade safeguards are retained; M67 had inadvertently omitted them in its NPC presentation sources.

## Follow-on, not included

NPC factions, threat tables, return-home pathing, patrols, hitstop and death-frame weapon drop are independent features. No implicit design decisions for them are hardcoded into M68.
