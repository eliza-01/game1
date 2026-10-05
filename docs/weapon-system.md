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

attachment follows the reference project contract: the imported weapon model pivot is the grip reference. melee uses the right weapon socket and bow uses the left weapon socket. the client follows the animated parent hand while keeping the weapon helper socket bind transform static.
