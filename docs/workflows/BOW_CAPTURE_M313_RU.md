# M313 · Restore melee / one-shot bow capture / correct arrow attachment

## Scope and rollback

This patch reverts **all M312-specific code** (including AIM debug, geometry module
and its obsolete test). The M310 hands/melee camera, attack-start ray,
HitStart→HitEnd, animated EquippedWeapon volume, sweep and headshot logic are
unchanged. Bow is deliberately separate at *target capture only*, not a second
combat controller.

## Bow flow

1. Player begins authored bow attack. Camera RMB controls, authored animation,
   server cooldown and release event are unchanged. No hitbox query and no
   periodic `BowAimUpdate` while drawing.
2. About 0.2 s before `Release` the client sends **one** camera ray and the
   currently rendered arrow socket position (explicit `ArrowNock` /
   `ArrowRelease` / `ArrowSocket` Attachment, else existing equipped hand Bone).
3. Server validates the ray, bounds the socket to RootCollider and, when
   available, server-visible hand Bone, and checks the short launch segment for
   walls. The server resolves closest **head/body** zone through the existing
   `EntityHitboxService`, with occlusion from world geometry. Its world-space
   point is frozen in the pending Release state. No client hit report.
4. Range is measured from the actual release socket rather than subtracting the
   socket-to-root distance; thus a close head within Range remains reachable.
   The validated socket offset is stored in RootCollider-local coordinates
   so walking during the capture-to-Release interval does not spawn an arrow
   at an old world position. At server-authored `Release`, one visual arrow
   moves from the validated launch point in a **straight line** to the frozen point with configured
   ArrowRegistry speed. No gravity, homing, predicted target position or second
   target scan. Range, lifetime and first-contact world/hitbox checks remain
   server-authoritative. A moved-away target receives no damage. Captured
   headshot classification may apply only when the same actor is actually hit.
5. If high latency prevents a snapshot from arriving before Release, the
   server uses the initial validated camera ray as a single fallback sample.
   This exceptional fallback is not homing or per-frame tracking.

## Embedding

- Landscape Painter's invisible `LandscapeSwayTarget` detects a candidate
  impact but **never owns the final surface point**. Resolve the first contact
  against the visible MeshPart's oriented bounding box (conservative, not
  exact mesh triangles), or ignore the proxy if no real part is intersected.
- Existing authored penetration remains configurable; for a thin rigid
  part it is capped by projected geometry thickness, preventing complete
  pass-through.
- Rigid moving objects use the existing `WeldConstraint`. Landscape Painter
  swaying objects are client-only anchored poses: an embedded arrow is saved
  once in the original model's pivot-local coordinates, then the existing
  `LandscapeSwayController:PivotTo` moves both together; no weld or extra loop.
  The client applies that pose once when the arrow first replicates.
- Skinned actors get a
  replicated Bone ObjectValue + tag. A single **client-only**, short-lived
  30 Hz renderer follows local `TransformedWorldCFrame`, including death
  animations not reproduced on the server. Stops when no arrows remain.
- All cosmetic arrows still expire after 2.5 s. There is no new arrow physics
  or damage processing loop.

## Studio Play acceptance

1. Hands and sword: original RMB facing, hit-zone headshot, multi-target
   volume sweep and authored windows still work on moving enemies.
2. Bow: shoot a stationary close/high head then body. Track server capture
   and release; headshot only on actual impact. Test both sides of 10/40 stud
   Range with moving target (a missed captured point stays a miss).
3. During monster Death, watch an embedded arrow follow the actual client
   bone instead of freezing in space/at feet. Test NPC run and ragdoll.
4. Hit hanging lantern under front/side/diagonal camera angles. It should
   lodge near the visible surface, sway with lantern and not jump to pivot.
5. Try a thin lantern with high Penetration settings, stone wall, mobile
   reticle and delayed network messages.

## Limits

The server cannot read client-side skinned mesh triangles or perfectly
reconstruct client pose, so head/body hitboxes are still approximations.
Arrow launch uses the locally rendered authored socket **only if validated**;
otherwise the existing conservative root-derived origin is used. This is a
performance- and security-conscious baseline that still requires live Roblox
Studio Play verification.
