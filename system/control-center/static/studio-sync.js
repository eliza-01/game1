/* M219: one client-side Studio Sync dispatcher, with scoped identities.
 * Domain-specific Studio implementations stay separate: houses own rig/physics
 * sync; decoration sync validates geometry and applies meshes in-place.
 */
window.game1StudioSync = (() => {
  const pending = new Set();
  const SLUG = /^[a-z0-9][a-z0-9_]{0,63}$/;
  async function run(domain, slug, {part = null} = {}) {
    if (!SLUG.test(String(slug || ''))) throw new Error('Studio Sync requires one registered asset slug');
    if (domain !== 'location' && domain !== 'real-estate') throw new Error('Unsupported Studio Sync domain');
    if (domain === 'location' && part !== null) throw new Error('Location Asset Sync is scoped to an entire asset');
    if (part !== null && (typeof part !== 'string' || part.length > 128 || /[\x00-\x1f]/.test(part))) {
      throw new Error('Invalid house mesh for Studio Sync');
    }
    const key = `${domain}:${slug}`;
    if (pending.has(key)) throw new Error(`Studio Sync is already running for ${slug}`);
    if (pending.size) throw new Error('Another Studio Sync is already running; one Studio Bridge command at a time');
    pending.add(key);
    try {
      const url = domain === 'location'
        ? '/api/location-assets/studio-sync'
        : `/api/real-estate/${encodeURIComponent(slug)}/sync`;
      const body = domain === 'location' ? {slug} : {part: part || ''};
      const result = await request(url, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
      });
      if (domain === 'location' && (result?.studio?.targetSlug !== slug ||
          Number(result.studio?.replacedModels) !== 0)) {
        throw new Error('Studio returned an unsafe or mismatched Location Asset Sync result');
      }
      return result;
    } finally {
      pending.delete(key);
    }
  }
  function locationSummary(slug, studio) {
    const count = Number(studio?.matchedModels || 0);
    const atlas = Number(studio?.parts || 0);
    const refs = Number(studio?.modelReferences || 0);
    const geometry = Number(studio?.geometryUpdated || 0);
    const meshes = Number(studio?.meshPartsUpdated || 0);
    const pending = Number(studio?.pendingGeometry || 0);
    return `Studio Sync ${slug} · placed instances ${count} · atlas IDs changed ${atlas}` +
      ` · geometry updated ${geometry} instance(s) / ${meshes} MeshPart(s)` +
      ` · model references changed ${refs}` +
      (pending ? ` · ${pending} instance(s) still need geometry review` : '') +
      (count === 0 ? ' · no matching authored instances found' : '') +
      '. Original placed Models and transforms retained.';
  }
  return Object.freeze({run, locationSummary});
})();
