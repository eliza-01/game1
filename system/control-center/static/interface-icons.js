(() => {
  const panels = ['monsters', 'buffs'];
  const key = 'game1.interface.section.v1';
  const loaded = new Set();
  const cardFor = (name, icon) => {
    const card = document.createElement('div');
    card.style.cssText = 'border:1px solid var(--line,#48505a);border-radius:8px;padding:8px;display:grid;justify-items:center;gap:6px';
    const caption = document.createElement('small');
    caption.textContent = name;
    card.append(icon, caption);
    return card;
  };
  // The atlas is shared with the model registry; no second icon catalog.
  window.game1MonsterPortrait = (data, name, size=32) => {
    const icon = document.createElement('span');
    const tile=data?.tiles?.find(t=>t.name===name)||data?.tiles?.find(t=>t.name==='Unknown');
    icon.style.cssText=`display:block;width:${size}px;height:${size}px;flex:none;image-rendering:pixelated`;
    if(tile){const scale=size/data.tileSize;icon.style.cssText+=`;background-image:url(monster-icons/atlas.png);background-size:${data.width*scale}px ${data.height*scale}px;background-position:-${tile.x*scale}px -${tile.y*scale}px`}
    else icon.textContent='—';
    icon.title=name||'Unknown';return icon;
  };
  const monsterTile = (data, tile) => cardFor(tile.name,window.game1MonsterPortrait(data,tile.name,64));
  const buffTile = (data, tile) => {
    const icon = document.createElement('span');
    icon.style.cssText = `display:grid;place-items:center;box-sizing:border-box;width:64px;height:64px;border-radius:4px;background:#1a1d25;border:2px solid ${tile.color}`;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = data.tileSize;
    canvas.style.cssText = 'width:72%;height:72%;image-rendering:pixelated';
    const ctx = canvas.getContext('2d');
    if (!ctx) throw Error('Canvas unavailable');
    ctx.fillStyle = tile.color;
    tile.mask.forEach((line, y) => [...line].forEach((pixel, x) => {
      if (pixel === '#') ctx.fillRect(x, y, 1, 1);
    }));
    icon.append(canvas);
    return cardFor(`${tile.name} · ${tile.grade}`, icon);
  };
  const load = (section) => {
    if (loaded.has(section)) return;
    const monsters = section === 'monsters';
    const host = document.getElementById(monsters ? 'monster-icon-atlas-preview' : 'buff-icon-preview');
    if (!host) return;
    loaded.add(section);
    fetch(monsters ? 'monster-icons/catalog.json' : 'buff-icons/catalog.json?v=547', {cache:'no-store'})
      .then(r => { if (!r.ok) throw Error(r.status); return r.json(); })
      .then(data => host.replaceChildren(...data.tiles.map(tile => monsters ? monsterTile(data, tile) : buffTile(data, tile))))
      .catch(err => { loaded.delete(section); host.textContent = 'Icon catalog unavailable: ' + err.message; });
  };
  const open = (section) => {
    for (const id of panels) {
      const active = id === section;
      const button = document.getElementById(`interface-nav-${id}`);
      document.getElementById(`interface-${id}-panel`).hidden = !active;
      button.classList.toggle('primary', active);
      button.setAttribute('aria-pressed', String(active));
    }
    try { localStorage.setItem(key, section); } catch {}
    load(section);
  };
  if (!document.getElementById('interface-nav-monsters')) return;
  for (const id of panels) document.getElementById(`interface-nav-${id}`).addEventListener('click', () => open(id));
  let initial = 'monsters';
  try { const saved = localStorage.getItem(key); if (panels.includes(saved)) initial = saved; } catch {}
  open(initial);
})();
