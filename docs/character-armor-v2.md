# Game1 — Character Armor Catalog v2

## Ownership and identities

| Entity | Example | Owns |
|---|---|---|
| Rig profile | `human` | Bone names, parent hierarchy and bind pose |
| Mesh family | `human_male_m001` | Reusable body shape sharing one rig profile |
| Mesh part | `human_male_m001_upper` | A slot's geometry, publication history and explicit `allowedGenders` |
| Atlas variant | `cloth_t001_upper_2048x2048_atlas.png` | Source image and Roblox Image Asset ID |
| Appearance | `atlas_123` | Reference to one atlas variant and future material settings |
| Armor set | `starter` | In-game identity, display name, type (`light` / `heavy` / `magic`) |
| Armor piece | `starter_upper` | Optional logical slot belonging to a set |
| Piece variant | `starter_upper / male` | Chosen geometry and appearance for a gender |

IDs identify **different concerns**. `starter` never appears in the mesh name and registering a mesh never creates a set. The same mesh and atlas may be referenced by any number of sets, without additional Roblox publication.

A set may contain any subset of `upper`, `lower`, `gloves`, `boots`, including no parts. A registered piece may have neither mesh nor appearance until authoring completes. That piece keeps the set in draft when selected for a character. An **absent** piece does not make the set incomplete.

`allowedGenders` is stored explicitly on each MeshPart. Mesh names suggest its initial selection at import; the catalog does not infer runtime permissions from names. A unisex variant is a *single* geometry/appearance pair eligible for both genders. Male or female variants override the unisex variant for the matching character gender; an explicitly incomplete override remains a draft rather than silently falling back.

## Authoring path

1. Create Armor set (name + light/heavy/magic). The stats section is intentionally a stub.
2. Add only the intended logical parts, with no required geometry or textures.
3. Register or publish reusable geometry in Rig & Parts, choosing Male, Female or Unisex in Inspect.
4. Register or publish Character atlases independently. `t001` is a texture naming convention, **not** the geometry identity.
5. From the geometry or atlas list use **→ Armor**. Pick the set, slot and gender, then save the variant. Choices are references, not copied assets.
6. Use the collapsed Debug/Startup Character assembly editor to choose a rig, explicit gender, set and face. Only published/current dependencies can activate a ready recipe.

The authoring database retains partial sets and pieces even when no Roblox asset has yet been published. The Studio runtime assembly is a resolved immutable projection of the current catalog, not a catalog editor. It chooses male/female/unisex references based on the character's explicit gender. Live equipment inventory, equipping events, stat application and material editing are **not** included in this iteration.

## FBX and face parts

**Canonical geometry names:** `<rig>_<male|female|common>_mNNN_<slot>` for *all* character meshes. Slots: `upper`, `lower`, `gloves`, `boots`, `head`, `eye_l`, `eye_r`, `eyebrow_l`, `eyebrow_r`, `hair`. Examples: `human_male_m001_head`, `human_male_m001_eye_l`, `human_male_m001_eyebrow_r`, `human_female_m001_hair`. `m001` is scoped to the gendered mesh family; it is NOT an armor set, texture or published revision. `human_common_m001_*` suggests unisex compatibility; the saved `allowedGenders` field remains authoritative. **The prefix must match the actual rig profile**, e.g. `human_armature` with `human_*` meshes.

Each eye and eyebrow side is an independent component and published MeshPart. The Blender extractor **does not join** left and right islands, and Character assemblies select each side explicitly using face slots. Missing optional facial components are allowed; Head remains mandatory. Both parts share the canonical `rig_carrier` and Bone contract. The temporary combined-face compatibility presenter is removed. This is an intentional clean cutover; old `head_01_male`, `eyes_01`, `eyebrows_01`, `hair_03_common` cannot be selected in new v2 recipes and must be re-authored/re-registered (and republished if required).

The main FBX armature is `human_armature`. A skinned accessory hair rig must be named `<full_mesh_part_name>_armature`; rigid pivot hair uses `hair_mount` and does not require a hair armature. Optional eye effect asset names extend an individual eye ID, e.g. `human_male_m001_eye_l_spiral`; they are not the normal face slot. Atlas/appearance identity stays independent: `t001` is a texture variant and is not baked into a MeshPart name.

A part's rig profile and bind pose must be compatible with the active rig. Changing metadata-only `allowedGenders` does not increment mesh content revision or force republishing. The Character builder still uses `rig_carrier`, proper bind alignment and `CharacterSkinWeld` for skinned parts; rigid pivot hair uses `hair_mount`.

## Current cutover

`schema_version=2` assemblies are the only modular recipes accepted by Roblox CharacterAssemblyBuilder. Existing v1 recipes are treated as drafts until explicitly saved in v2; there is **no** adapter that silently derives an armor set from an old component name. Existing Roblox Model/Image IDs may be reused when valid but do not define the new armor identity. Old v1-specific automated tests must be replaced with tests for the new contracts rather than used as proof of v2 compatibility.

## API contracts

- `GET /api/armor` — read the set/part/variant catalog and available resources.
- `POST /api/armor/sets` — create or edit an armor set with optimistic revision.
- `POST /api/armor/pieces` — create an optional part.
- `POST /api/armor/pieces/remove` — remove a part (the mesh and atlas remain intact).
- `POST /api/armor/variants` — assign nullable `meshPartId` and `atlasVariantId` to `unisex`, `male` or `female`.
- `POST /api/characters/components/compatibility` — metadata-only change of a published or draft MeshPart's allowed genders.
- `POST /api/characters/assemblies` — save explicit-gender v2 Character debug/startup recipe.

All catalog writes use the same SQLite database (`.control-center/game1.db`) as the Character registry, enforce validation server-side, and re-export the resolved Character registry. No legacy `componentId → atlas` ownership in the new authoring path.
