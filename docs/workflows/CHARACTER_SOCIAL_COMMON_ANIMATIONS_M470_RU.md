# M470 · numbered animations · human_common · social catalog

## Canonical file names (all categories)

Every new animation file ends with `_01`, `_02`, etc. The semantic state is
independent of its numbered variant: `base_jump_start_01` is `base.jump_start`
variant `01`, and `social_laugh_02` is `social.laugh` variant `02`.

Examples:
- `human_common_social_laugh_02.rbxm` → `human_male_social_laugh_02` **and**
  `human_female_social_laugh_02`; one published Roblox Animation ID, version 02.
- `human_male_social_laugh_01.rbxm` is separate and remains available after
  an authoritative common `laugh_02` is added.
- `human_female_base_jump_start_01.rbxm`, `human_common_social_waiting_01.rbxm`,
  `human_male_1hs_attack_02.rbxm`, `human_female_emotions_sad_01.rbxmx`.
- `social_sp_wait_01` is action `sp_wait`, version 01; `social_waiting_01` is
  action `waiting`, version 01, replacing the former `waiting_a` name.

## Semantic actions

Both human genders have these 13 Social actions, each with independent variants:
`atk`, `bow`, `clap`, `dance`, `hi`, `laugh`, `no`, `sad`, `sp_wait`, `unaware`,
`victory`, `waiting`, `yes`. `social.sad` and `emotions.sad` remain separate.

## Ownership and priority

`human_common_*` is one virtual publication owner for the Human family, not
another playable character. The scanner accepts common filenames while viewing
Male or Female. After approval, the shared registry makes the *same version*
available to both genders without duplicating source files or Roblox uploads.

Resolution is per version: an explicit common version overrides only that
number; a personally published version with a different number remains available.
A manually shared Male/Female source is a fallback **for that exact version**.
`Social.Resolve(character, "laugh_02")` selects the specific numbered variant.
Without a requested version the existing weighted-selection behavior applies.
The same merge policy is shared between Studio test stand, client player,
face presentation and the server attack validator.

Common publication checks both authored rigs for compatibility. Body gestures
may ignore unused face sockets, while `atk` and `victory` still validate
weapon-grip compatibility. Published ID does not prove that the keyframes
actually animate both rigs as intended; Studio Play verification is needed.

## Migration and installation

Install M470 **on top of M469**, without M466. Run
`system/control-center/migrations/m470_animation_versions.py` only after the
patch checks/tests. The migration converts historical `variant=0` to `_01` in
all scopes, including renamed `waiting_a`, preserving every published Roblox
Animation ID and publication history. It backs up SQLite; repeated runs are
idempotent and an existing conflicting version stops the migration. Existing
source files are renamed when available; files excluded from diagnostics
retain their stored paths rather than gaining broken synthetic paths.

Finally run `verify.py`, install plugin, restart Control Center, sync Rojo,
and test both genders in Studio Play. Unversioned **new** files are not
accepted by the scanner.
