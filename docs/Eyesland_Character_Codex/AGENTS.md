# Eyesland Character — binding agent instructions

This directory is a **work package for a Codex agent with Blender MCP**. The agent must read `docs/TECH_SPEC.md` in full, inspect `refs/01_PRIMARY_CHARACTER_CONCEPT.png`, and load `contract/rig_contract.json`, `contract/equipment_regions.json`, and `contract/seam_contract_template.json` before creating geometry.

Your job is to actually create and save a functional, editable Blender rig and 15 skinned body meshes matching the reference. Do not respond with a plan only; produce `.blend`, `.fbx`, validation scripts, reports and preview test assets in `deliverables/`.

## Fixed product decisions

- Eyesland uses **one fully custom unisex rig**, **not** Roblox R15/R6 or marketplace avatar.
- Fully bald whole head; one future whole-hair attachment; no hair geometry in this task.
- Strict, measurable **X-mirror symmetry** for body geometry, materials, bones, weights, sockets. `.L` is character's anatomical left, world +X at rest.
- One permanent common skeleton. Every future armor shape shares **the exact source bind rig**. Variants don't introduce character skeletons.
- 15 independently replaceable skinned BODY_BASE objects, consistent seam ring contract. Same mesh+UV may use alternative textures, different silhouette must use alternate skinned mesh.
- Weapon grips on BOTH hands independent of shield attachments on BOTH forearms. Never parent a shield to a weapon grip. Shoulders are independent attachment bones; cape has a central back mount and two symmetrical clasp attachments; hair has a head-mounted anchor.
- Match main character sheet visual style except symmetrical details and absence of hair. Never let temporary QA proxies appear in game export.
- Use Blender Python `bpy` **through connected Blender MCP**. Output stored on disk and QA check reproducible. Reference files are read-only.
- Do not arbitrarily overwrite existing `.blend`, rename the project's stable bones, or modify the Roblox game.

## Execution checkpoints

1. Establish MCP connectivity and inspect Blender scene and available APIs.
2. Create & save canonical mesh proportions and armature. Produce a real Blender file early, then create incremental checkpoints.
3. Create each body mesh with proper skinning and UV; seam profiles, symmetrical weights, sockets.
4. Provide technical proxy assets under TEST_ONLY__NO_EXPORT, swap preview, pose checks and numeric validator.
5. Run validator, fix issues, export FBX and if correct GLB, re-import in isolated scene and compare bind rig.
6. Save QA report listing PASS / FAIL / NOT_TESTED (never pretend a missing test passed).
7. Summarize output locations and any remaining technical risks.

**Stop-on-failure:** If no Blender MCP connection, user permission, or Blender executable is available, say exactly what is blocked. Never claim assets exist that were not saved. Don't substitute AI-rendered pictures for real Blender meshes.
