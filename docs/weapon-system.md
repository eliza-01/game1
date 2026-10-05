# game1 weapon system

canonical identity is the weapon `slug`. new weapons derive it from the english name as lowercase snake_case; existing slugs stay stable across revisions.

source layout:

```text
assets/source/weapons/<type>/<slug>/model/<slug>.fbx
assets/source/weapons/<type>/<slug>/textures/<texture-slot>.<ext>
```

prepared assets mirror the same tree under `assets/prepared/weapons`. roblox publication ids are stored in sqlite, `assets/manifests/weapons.json`, and the generated runtime `src/shared/weapon/WeaponRegistry.luau`.

weapon stats are additive modifier sources. the first exposed modifiers are `Damage` and `AttackSpeed`; zero means no change and negative values subtract. character baselines are Damage 10, AttackSpeed 100, RunSpeed 50. the stat service composes modifiers by source so future armor/buffs do not need to overwrite weapon math.

weapon types are also animation contexts: `1hs`, `2hs`, `bow`. unarmed uses `hands`.

attachment is runtime-canonical. on every equip the server discards any stale `Game1WeaponGrip` orientation from the Studio template (or creates the grip if an old template has none), preserves only its authored grip point, and rebuilds one `Game1WeaponGrip` with canonical world XYZ axes. every weapon therefore uses one solver and never falls back to `Model:PivotTo(socketFrame)`. the target weapon socket is rotated -90 degrees around its local X axis before `desiredSocket * currentGrip^-1` alignment. melee uses the right weapon socket and bow uses the left weapon socket. this global rule is independent of per-asset pivot orientation and cannot accumulate rotation per frame.
