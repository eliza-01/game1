/* Location Assets publication policy. Pure UI decisions; no network or Studio.
 * Never queue replacement of an already published shared atlas. */
window.game1LocationPublication = (() => {
  const variantFor = (item, catalog = []) => {
    const id = Number(item?.atlasVariantId || 0);
    if (!id) return null;
    return (item?.atlasVariants || []).find(v => Number(v.id) === id) ||
      catalog.flatMap(family => family.variants || []).find(v => Number(v.id) === id) || null;
  };
  // Only FBX files with genuine Bones need a carrier. Never create dummy
  // skeletons for static Location Assets or queue a pointless Model publication.
  const needsCanonicalFbx = item => Boolean(item?.model_path && item?.fbxAnalysis?.meshes &&
    item.fbxAnalysis.meshes.some(m=>Array.isArray(m.bones) && m.bones.length>0) &&
    !item.fbxAnalysis.meshes.some(m=>String(m.name).toLowerCase()==='rig_carrier'));
  function plan(item, catalog = [], hasNewFbx = false) {
    const selected = item?.appearanceMode === 'material' ? null : variantFor(item, catalog);
    const modelNeeded = Boolean(hasNewFbx || needsCanonicalFbx(item) || (item?.model_path &&
      (!item.model_asset_id || item.model_sha256 !== item.model_published_sha256)));
    const atlasNeeded = Boolean(selected && !selected.retired && !selected.published_id);
    const reviewRequired = Boolean(selected && !selected.retired && selected.published_id && !selected.current);
    // MeshPart overrides can refer to independent atlas families while the
    // Location Asset default uses Material. These publications are NOT owned by
    // the default binding. Resolve each variant directly from the shared catalog.
    const variants = new Map(catalog.flatMap(family => family.variants || [])
      .map(variant => [Number(variant.id), variant]));
    const meshAtlases = new Map();
    const unresolvedMeshAtlases = [];
    for (const [meshName, settings] of Object.entries(item?.meshOptions || {})) {
      if (!settings || !['atlas', 'material_atlas'].includes(settings.appearanceMode)) continue;
      const id = Number(settings.atlasVariantId || 0);
      if (!Number.isSafeInteger(id) || id <= 0) continue; // inherited default
      const variant = variants.get(id);
      if (!variant || variant.retired) {
        unresolvedMeshAtlases.push({meshName, variantId: id});
      } else if (!variant.published_id) {
        const pending = meshAtlases.get(id) || {id, filename: variant.filename, meshNames: []};
        pending.meshNames.push(meshName);
        meshAtlases.set(id, pending);
      }
    }
    return {variant: selected, modelNeeded, atlasNeeded, reviewRequired,
      meshAtlases: Array.from(meshAtlases.values()).sort((a, b) => a.id - b.id),
      unresolvedMeshAtlases,
      count: Number(modelNeeded) + Number(atlasNeeded) + meshAtlases.size};
  }
  return Object.freeze({plan,needsCanonicalFbx});
})();
