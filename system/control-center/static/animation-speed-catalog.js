// Pure, published-animation selectors shared by UI and regression tests.
// Preserve each published Roblox Asset ID as the single override identity.
(function (root) {
  'use strict';
  const text = value => String(value ?? '').toLowerCase();
  const normalize = value => text(value).replace(/[_./\\-]+/g, ' ').replace(/\s+/g, ' ').trim();
  function searchable(clip) {
    const consumers = Array.isArray(clip.availableFor) ? clip.availableFor : [];
    return [clip.name, clip.kind, clip.subject, clip.channel, clip.scope,
      clip.weaponSet, clip.clipId, clip.assetId, ...consumers]
      .map(normalize).join(' ');
  }
  function visible(catalog, {search = '', kind = '', subject = ''} = {}) {
    const tokens = normalize(search).split(' ').filter(Boolean);
    return (catalog || []).filter(clip => {
      if (kind && clip.kind !== kind) return false;
      const consumers = Array.isArray(clip.availableFor) ? clip.availableFor : [];
      if (subject && clip.subject !== subject && !consumers.includes(subject)) return false;
      const haystack = searchable(clip);
      const words = haystack.split(' ');
      return tokens.every(token =>
        token === 'male' || token === 'female' ? words.includes(token) : haystack.includes(token)
      );
    }).sort((left, right) => {
      const a = [left.kind, left.subject, left.scope, left.weaponSet, left.name, left.assetId];
      const b = [right.kind, right.subject, right.scope, right.weaponSet, right.name, right.assetId];
      for (let i = 0; i < a.length; i += 1) {
        const compare = text(a[i]).localeCompare(text(b[i]));
        if (compare) return compare;
      }
      return 0;
    });
  }
  function subjects(catalog, kind = '') {
    const all = new Set();
    for (const clip of catalog || []) {
      if (kind && clip.kind !== kind) continue;
      if (clip.subject) all.add(clip.subject);
      for (const subject of clip.availableFor || []) all.add(subject);
    }
    return Array.from(all).sort();
  }
  function page(rows, index = 0, size = 24) {
    const pages = Math.max(1, Math.ceil(rows.length / size));
    const number = Math.min(Math.max(0, index), pages - 1);
    return {rows: rows.slice(number * size, (number + 1) * size), number, pages};
  }
  const api = Object.freeze({visible, subjects, page});
  root.game1AnimationSpeedCatalog = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
