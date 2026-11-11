# M286 · Direct-manipulation Landscape Painter / Studio admin Timeline

## Landscape Painter · Edit mode

The branch and asset tools reuse `LandscapeAdjustments`, a UI-only ModuleScript.
It neither changes Workspace nor owns a second asset catalogue.

- Thickness and tether length are logarithmic sliders (fine control at small values), with live viewport feedback. Drag on the track; click the current number only if an exact value is needed.
- Yaw/Pitch/Roll are separate direct-manipulation sliders with reset and quick Yaw 90-degree presets.
- Color uses a preset strip, hue strip and saturation/brightness pad. Hex is optional and hidden until clicked.
- Changing an in-progress branch affects the visual preview, not previously committed segments. The Play/Place geometry is only changed on confirmed click/Apply.
- Continuous slider changes are bounded to ~30 preview updates/second; branch preferences persist in bounded batches, not every pointer event.
- `Use` is a persisted profile applied to future placements. While it is enabled, profile values override the draft controls; this is explicitly stated in the panel. `Apply` continues to operate on the selected managed Studio model. Saving a new profile selects it but does not automatically enable Use.

## Attack Timeline · Edit mode

- For `subjectType = characters`, find `CharacterRegistry.studioAdminArchetypeId`, require matching `subjectId` and a READY assembly v2, and build it through the existing `StudioCharacterStandBuilder` (which uses `CharacterAssemblyBuilder`). Do not load only the invisible rig as a visual preview.
- For monsters, keep loading their published Model asset, with no change in protocol.
- The model lives only inside the plugin's WorldModel. No new mannequin in Workspace; no save/Undo operation, no gameplay spawning.
- Pose samples still come from the published KeyframeSequence and never from attack timeline metadata. Existing HitStart/HitEnd confirmation and server validation remain unchanged.
- For rigid pivot hair, the timeline invokes the **same** `HairAttachmentController.UpdateCharacter` method per sampled frame, without starting a RenderStepped loop.
- Missing admin, mismatched subject, empty visual geometry or inaccessible source build are explicit errors; do not silently fall back to an invisible rig.

## Studio acceptance checklist (not performed offline)

1. In Edit, set `Human Female` as Studio admin, open `hands_attack_01`. The entire character including armor, eyes, hair and textures appears and scrubs in the plugin ViewportFrame. The model does not appear in Workspace.
2. Move the head during a scrub; pivot hair moves with the canonical mount. Reopen an attack; there are no leftover previews.
3. Open a monster attack; preview still uses the published monster model.
4. In Landscape Painter drag diameter, length and angles: previews update immediately; numeric exact input is not required. Test surface branches follow levels 0–4; no ghost parts are saved.
5. Save a profile, use it for successive placements, disable Use, then apply the saved profile to a selected existing Landscape Painter model. Undo remains one operation per confirmed placement/apply.
6. Reopen Studio: saved branch preferences and saved named profiles are retained. No change to DecoManager.
