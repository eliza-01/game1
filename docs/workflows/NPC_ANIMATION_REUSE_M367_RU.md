# M367 · Connect existing NPC animations

NPC → Animations → `connect existing animations`: select a distinct registered NPC,
choose any published, current source actions (`weapon_set`, `slot`, `variant`),
then Connect. An occupied target coordinate is never silently replaced.

`POST /api/npc-animations/connect` accepts `{targetNpc,sourceNpc,bindingIds}`.
All items are validated and inserted in one SQLite transaction; rejects local,
changed, borrowed, duplicate or unknown source bindings. No schema migration:
`monster_animation_bindings.clip_id` already references a clip. Linked bindings
have independent options (`weight`, `disarm`, `compatible_sets`) and retain
source clip publication identity, source bytes and asset ID. The normal export
renders them under the destination NPC's runtime registry profile.

The source NPC owns its clip and publication history. Removing its clip/NPC
is rejected while any other NPC references it. First disconnect recipients.
Disconnecting a recipient removes only its binding; it does not retire or
republish the donor clip. Re-scanning a recipient's local animation of the
same coordinate creates its own clip and never rewrites donor metadata.

Rig compatibility is advisory: differing skeleton structure signatures show a
warning in the editor; playback still needs verification in Roblox Studio.
The endpoint does not access Roblox Cloud or files. Runtime consumes the
existing `NpcAnimationRegistry.luau` without any new per-frame processing.
