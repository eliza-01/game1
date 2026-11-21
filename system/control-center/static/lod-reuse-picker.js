/* Shared LOD1 reuse chooser for Location Assets and Real Estate (M411).
 * The host is authoritative: this UI never accepts arbitrary Roblox Model IDs.
 */
window.game1LodReusePicker = (() => {
  async function pick(targetDomain, targetSlug) {
    const response = await request('/api/lod1-library');
    const items = (Array.isArray(response?.items) ? response.items : [])
      .filter(x => x && (x.domain === 'location' || x.domain === 'house' || x.domain === 'house_part') &&
        !(x.domain === targetDomain && x.slug === targetSlug));
    if (!items.length) throw Error('Нет опубликованных LOD1 для повторного использования.');
    return new Promise(resolve => {
      const d = document.createElement('dialog');
      d.className = 'lod-reuse-dialog';
      const title = document.createElement('h3'); title.textContent = 'Выбрать опубликованный LOD1';
      const note = document.createElement('p');
      note.textContent = 'Повторно используется Roblox Model ID, без загрузки FBX. Проверь совпадение пропорций, масштаба и pivot.';
      const search = document.createElement('input');
      search.placeholder = 'Поиск по названию или Model ID'; search.setAttribute('aria-label', 'Поиск LOD1');
      const domain = document.createElement('select');
      for (const [value,label] of [['all','Все разделы'],['location','Location Assets'],['house','Real Estate'],['house_part','House parts']]) {
        const option=document.createElement('option'); option.value=value; option.textContent=label; domain.appendChild(option);
      }
      const filters = document.createElement('div'); filters.className='lod-reuse-filters';
      filters.append(search,domain);
      const list=document.createElement('div'); list.className='lod-reuse-list';
      const cancel=document.createElement('button'); cancel.type='button'; cancel.textContent='Отмена';
      let done=false;
      const finish=value=>{if(done)return; done=true;d.close();d.remove();resolve(value);};
      cancel.onclick=()=>finish(null);
      d.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
      const render=()=>{
        list.replaceChildren();
        const query=search.value.trim().toLowerCase();
        const visible=items.filter(x=>(domain.value==='all'||domain.value===x.domain)&&
          (!query||`${x.slug} ${x.modelAssetId}`.toLowerCase().includes(query)));
        if(!visible.length){const empty=document.createElement('p');empty.textContent='Нет подходящих LOD1';list.appendChild(empty);}
        for(const item of visible){
          const row=document.createElement('div');row.className='lod-reuse-row';
          const info=document.createElement('div');
          const name=document.createElement('strong');name.textContent=item.slug;
          const metadata=document.createElement('small');
          metadata.textContent=`${item.domain==='house'?'Real Estate':item.domain==='house_part'?'House part':'Location Assets'} · Model ID ${item.modelAssetId} · rev ${item.revision}`;
          info.append(name,metadata);
          const use=document.createElement('button');use.type='button';use.textContent='Использовать';
          use.onclick=()=>finish(item);
          row.append(info,use); list.appendChild(row);
        }
      };
      search.addEventListener('input',render); domain.addEventListener('change',render);
      d.append(title,note,filters,list,cancel);
      document.body.appendChild(d); render();
      if(typeof d.showModal==='function') d.showModal();
      else finish(null);
      search.focus();
    });
  }
  function payload(item, expectedRevision) {
    return {sourceDomain:item.domain, sourceSlug:item.slug, sourceRevision:item.revision,
      sourceModelAssetId:item.modelAssetId, expectedRevision};
  }
  return Object.freeze({pick,payload});
})();
