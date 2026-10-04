# game1 character animation system

## canonical contract

one studio-exported `.rbxm`/`.rbxmx` clip maps to one permanent roblox animation asset id.

runtime never resolves an animation by filename. the chain is:

`character state/action -> semantic slot -> character animation profile -> binding -> clip -> roblox asset id`

character animation profiles are attached to a registered character archetype and record that archetype's skeleton signature. a changed skeleton is surfaced as incompatible until the profile is reviewed/rescanned.

## scopes

base scope is character-wide and independent of equipped weapon:

- `idle`, `walk`, `run`
- `jump_start`, `jump_loop`, `fall`, `land`
- `seated.enter`, `seated.loop`, `seated.exit`

weapon scope is a context overlay. m5.1 starts with `hands`, `1hs` and `bow`:

- `idle`, `combat_idle`, `walk`, `run`
- `attack` with variants `01..n`
- `special_attack` with variants `01..n`
- `equip`, `unequip`
- `bow` additionally supports `aim`

`hands` is the canonical unarmed weapon context. newly spawned characters request `hands` first and fall back to base slots when a hands-specific clip is absent.

variants are alternate visuals of the same gameplay action. for example `1hs_attack_01` and `1hs_attack_02` both bind to slot `attack`; the resolver chooses by weight.

## canonical files

registered clips are copied into both recoverable source and publication-ready prepared trees:

`assets/source/characters/<race>/<gender>/<character>/animations/...`

`assets/prepared/characters/<race>/<gender>/<character>/animations/...`

examples:

- `base/base_idle.rbxm`
- `base/base_seated_enter.rbxm`
- `weapons/1hs/1hs_attack_01.rbxm`
- `weapons/bow/bow_run.rbxm`

## scan naming

preferred new-project names may include the selected character prefix or omit it:

- `human_female_idle.rbxm` or `idle.rbxm`
- `human_female_hands_idle.rbxm` or `hands_idle.rbxm`
- `human_female_hands_attack_01.rbxm`
- `human_female_1hs_attack_01.rbxm`, `human_female_1hs_attack_02.rbxm`
- `human_female_bow_run.rbxm`, `human_female_bow_aim.rbxm`

canonical pattern: `[character_]context_slot[_variant]`. the character prefix is stripped only when it matches the selected animation profile.

scanner also accepts the proven reference naming forms such as `Wait_1HS_*`, `AtkWait_1HS_*`, `Atk01_1HS_*`, `Run_Bow_*`, and `SpAtk02_Bow_*` without importing the old game's taxonomy into runtime.

unrecognized filenames are not discarded. the asset manager shows them under `unassigned`, where context (`base`, `hands`, `1hs`, `bow`), semantic slot and variant can be selected manually. manual assignment uses the same canonical source/prepared storage and registry path as automatic scan classification.

## publication

`publish missing` publishes local-only clips sequentially. already-published clips keep their permanent asset id. if their local bytes change, status becomes `changed`; m5 does not create a duplicate id. animation content-version updates remain a separate studio-bridge operation because open cloud content update does not currently support animation rbxm content.

## m5 runtime boundary

m5 deliberately keeps gameplay and presentation separate. the existing movement controller remains the owner of physics and publishes `MovementState`; the animation controller consumes that presentation state.

wired now:

- base/weapon `idle`, `walk`, `run`
- weapon `attack` variants through the existing lmb attack input
- reverse playback of `walk` while the existing backpedal presentation flag is active
- character/skeleton compatibility checks and track prewarm

registered now but reserved for their gameplay/state owner:

- airborne (`jump_start`, `jump_loop`, `fall`, `land`)
- seated transitions (`seated.enter`, `seated.loop`, `seated.exit`)
- combat stance (`combat_idle`), special attack, equip/unequip and bow aim

this keeps the semantic contract stable without pretending that an animation clip itself owns physics, posture or combat state.

## subsystem layout

control-center animation code is split by responsibility instead of growing one service file:

- `animation_core/common.py` — canonical slots, weapon sets and filename classification
- `animation_core/storage.py` — sqlite profiles/clips/bindings and scan/import
- `animation_core/publication.py` — sequential publication rules
- `animation_core/registry.py` — portable manifest and generated luau registry
- `animation_store.py` — small compatibility facade used by the host agent
