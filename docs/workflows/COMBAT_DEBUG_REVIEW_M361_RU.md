# M361 · Studio melee debugging and hit effects: code review

## Findings verified in source

1. M360 rebuilt 69 anchored Parts (64 sectors, four boundaries, one aim ray) at 15 Hz, including a ground Raycast, producing discontinuous presentation. Sampling speed was mistaken for positional refresh rate.
2. Separate debug hitbox contact classification runs at 8 Hz when enabled. This is deliberate diagnostic feedback; it is **not** the server's authoritative HitEnd snapshot. It cannot apply damage.
3. Both effect pools ran idle RenderStepped handlers forever, even with all sparks disabled.
4. Test Loadout destruction detached the radius handler but did not detach the hitbox handler / destroy its pooled Parts.
5. Server `AttackDamageResolver` called `HitEffectService.Publish` even when `DamageService.Apply` returned zero. This could show a spark without lost HP. It does not by itself explain every reticle flash.
6. Headshot aim guide was an emissive Neon Part that could pass in front of the camera. Its appearance should not be confused with a server-generated spark. No source path makes Test Loadout *emit* `CombatHitEffect` by itself.

## Changes

- Melee outline now consists of client-only Beam instances on RootCollider attachments. It follows character movement and yaw without redraw; geometry rebuilds only on root/radius/arc/height change. Ground Raycast removed, because the server's damage sector is rooted in RootCollider, not the ground surface. The guide stays camera-relative, non-emissive, and never participates in physics queries.
- Contact coloring remains a sampled 8 Hz Studio visualization. UI label shows its rate and a cumulative sample count, so debug cadence remains observable. Target model enumeration remains once/second from CollectionService rather than full Workspace.
- On GUI destruction, both subscriptions and visual pools are destroyed.
- A damage spark is published only for `finalDamage > 0`.
- A single shared HitSparkPoolTicker subscribes to RenderStepped only during actual pooled spark playback and disconnects after the last spark finishes.

## Studio verification required

- Move, strafe, rotate, jump, change AttackRadius and MeleeArcAngle; confirm outline follows without positional steps; compare with server HitEnd in moving-target scenarios.
- Toggle both debug overlays repeatedly; observe `Game1AttackRadiusPreview`, `Game1TargetHitboxPreview`, and `MeleeArcDebugAnchor` cleanup after deactivation/respawn/GUI destruction.
- With no attack, confirm no `_Game1LocalHitEffects` or `_Game1LocalWeaponBounceEffects` spark activation. If flashes remain: inspect which pool is active. A static code review cannot prove the visual origin on a specific Studio Place.
- Test shielded/zero-damage contacts, weapon bounce into solid assets, multi-target hits, and critical/headshot effects.
- Measure client Lua/RenderStepped/Beam rendering with MicroProfiler. Beam vs Part GPU costs vary by device, so no absolute FPS gain is claimed without measurement.
