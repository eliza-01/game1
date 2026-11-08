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
    const selected = variantFor(item, catalog);
    const modelNeeded = Boolean(hasNewFbx || needsCanonicalFbx(item) || (item?.model_path &&
      (!item.model_asset_id || item.model_sha256 !== item.model_published_sha256)));
    const atlasNeeded = Boolean(selected && !selected.retired && !selected.published_id);
    const reviewRequired = Boolean(selected && !selected.retired && selected.published_id && !selected.current);
    return {variant: selected, modelNeeded, atlasNeeded, reviewRequired,
      count: Number(modelNeeded) + Number(atlasNeeded)};
  }
  return Object.freeze({plan,needsCanonicalFbx});
})();
