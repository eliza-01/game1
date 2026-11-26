(() => {
  const host=document.getElementById('monster-icon-atlas-preview');
  if(!host)return;
  fetch('monster-icons/catalog.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(data=>{
    for(const tile of data.tiles){
      const card=document.createElement('div');card.style.cssText='border:1px solid var(--line,#48505a);border-radius:8px;padding:8px;display:grid;justify-items:center;gap:6px';
      const icon=document.createElement('span');icon.style.cssText=`display:block;width:64px;height:64px;image-rendering:pixelated;background-image:url(monster-icons/atlas.png);background-size:${data.width*4}px ${data.height*4}px;background-position:-${tile.x*4}px -${tile.y*4}px`;
      const caption=document.createElement('small');caption.textContent=tile.name;card.append(icon,caption);host.append(card);
    }
  }).catch(err=>{host.textContent='Atlas unavailable: '+err.message});
})();
