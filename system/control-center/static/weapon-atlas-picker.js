/* Weapons and arrows are consumers of the SAME atlas editor used for Location
 * Assets / Real Estate. No custom dot rendering or separate atlas state store.
 * Attaching/selecting never publishes an Image or mutates Studio. */
window.game1WeaponAtlasPicker = (() => {
  let catalog = [], loading = null;
  const states = new Map();
  const editor = () => window.game1ConsumerAtlasEditor;
  function stateFor(kind, slug) {
    const key = `${kind}:${slug}`;
    if (!states.has(key)) states.set(key, editor().newState());
    return states.get(key);
  }
  async function refresh() {
    if (!loading) loading = request('/api/texture-atlases').then(data => {
      catalog = data.families || [];
    }).finally(() => { loading = null });
    await loading;
  }
  function variantsFor(kind, item) {
    if(!item)return {currentId:0,linked:[],familyVariants:[]};
    const bound=item.atlas_binding;
    const stored=kind==='weapon'?(item.textures||[]).filter(v=>v.asset_id):
      item.texture_asset_id?[{source_path:item.texture_path,asset_id:item.texture_asset_id}]:[];
    const legacy=!bound?stored.map((v,i)=>({id:-(i+1),legacy:true,
      filename:String(v.source_path||'').split(/[\\/]/).pop(),resolution:'legacy',
      published_id:v.asset_id,current:true})):[];
    const linked=[...(item.atlas_variants||[]),...legacy];
    const familyKeys=new Set([...(item.atlas_variants||[]),...(bound?[bound]:[])]
      .map(v=>v.atlas_key||v.atlasKey).filter(Boolean));
    const attached=new Set(linked.map(v=>Number(v.id)));
    const familyVariants=catalog.filter(f=>familyKeys.has(f.atlasKey))
      .flatMap(f=>f.variants||[]).filter(v=>v.current&&!attached.has(Number(v.id)));
    return {currentId:Number(bound?.id||0),linked,familyVariants};
  }
  function summary(kind,item) {
    return editor().previewDots(variantsFor(kind,item));
  }
  function render(id, kind, item, reload) {
    const host = $(id);
    if (!host) return;
    if (!item) {
      host.innerHTML = '<small class="muted">Register the asset to attach an atlas.</small>';
      return;
    }
    const state = stateFor(kind, item.slug);
    const bound = item.atlas_binding;
    const stored = kind === 'weapon' ? (item.textures || []).filter(v=>v.asset_id)
      : item.texture_asset_id ? [{source_path:item.texture_path,asset_id:item.texture_asset_id}] : [];
    const selectedVariant = (item.atlas_variants || []).find(v=>Number(v.id)===Number(bound?.id));
    // Historical source textures must not be mistaken for an active legacy atlas
    // once the user selects a new standardized shared variant.
    const legacy = !bound ? stored : [];
    const oldActive = bound && selectedVariant?.original_filename &&
      selectedVariant.original_filename !== selectedVariant.filename ? [selectedVariant] : [];
    const legacyWarning = legacy.length || oldActive.length;
    const standard = bound?.filename || '<atlas_key>_<width>x<height>_atlas.png';
    const nonstandard = oldActive.length || legacy.some(v=>!/^.+_[1-9]\d*x[1-9]\d*_atlas\.(png|jpe?g)$/i
      .test(String(v.source_path||'').split(/[\\/]/).pop()));
    // Preview historical Image IDs as dots immediately. This is a read-only UI
    // projection, not a hidden DB migration or a second Atlas Registry.
    const virtual = !bound ? stored.map((v,i)=>({id:-(i+1),legacy:true,
      filename:String(v.source_path||'').split(/[\\/]/).pop(),resolution:'legacy · index to resolve',
      published_id:v.asset_id,current:true})) : [];
    // Resolution grades of an attached atlas family are discoverable through
    // the SAME shared AtlasRegistry, even before explicitly attaching each
    // size to this consumer. No implicit binding is written when rendering.
    const attachedIds = new Set((item.atlas_variants||[]).map(v=>Number(v.id)));
    const familyKeys = new Set([...(item.atlas_variants||[]),...(bound?[bound]:[])]
      .map(v=>v.atlas_key||v.atlasKey).filter(Boolean));
    const familyVariants = catalog.filter(f=>familyKeys.has(f.atlasKey))
      .flatMap(f=>f.variants||[]).filter(v=>v.current&&!attachedIds.has(Number(v.id)));
    const options = {
      consumerType:kind,
      slug:item.slug,
      currentId:Number(bound?.id || 0),
      getCurrentId:() => Number(item?.atlas_binding?.id || 0),
      linked:[...(item.atlas_variants||[]),...virtual],
      familyVariants,
      catalog,
      revision:Number(bound?.revision || 0),
      getRevision:()=>Number(bound?.revision || 0),
      // Exact same Location/Real Estate reviewed atlas publication workflow.
      // Weapon and Arrow never publish an image in their Model operation.
      allowUpload:true,
      filePicker:'/api/files/choose-location-asset-texture',
      onIndexLegacy:async()=>{
        if(!confirm(`Index published legacy Image IDs for ${kind} ${item.slug}? No Open Cloud upload or Studio Sync.`))return;
        const result=await request('/api/texture-atlases/index-existing-weapons',{
          method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true,kind,slug:item.slug})});
        const summary=`Indexed ${result.indexed.length} · skipped ${result.skipped.length}`;
        const status=$(kind==='arrow'?'arrow-operation-status':'weapon-operation-status');
        if(status)status.textContent=summary;
        toast(summary + (result.skipped.length?` · ${result.skipped.map(v=>v.reason).join('; ')}`:''),
          Boolean(result.skipped.length));
      },
      onRefresh:async () => {
        await reload(); await refresh();
        // The shared UI must not rerender with stale binding revisions.
        const resource = await request(kind==='arrow'?'/api/arrows':'/api/weapons');
        item = (resource.items||[]).find(row=>row.slug===item.slug) || item;
      },
      onRender:() => render(id,kind,item,reload),
      onMessage:(message,failed=false) => {
        const status = $(kind==='arrow'?'arrow-operation-status':'weapon-operation-status');
        if(status) status.textContent = message;
        toast(message,failed);
      },
    };
    const legacyHtml = legacyWarning ? `<div class="game1-atlas-legacy" role="status">
      <strong>${nonstandard?'Legacy atlas / нестандартное имя':'Legacy Image ID / требуется привязка к реестру'}</strong>
      <span>Текущая текстура: ${[...legacy,...oldActive].map(v => esc(v.original_filename||String(v.source_path||'').split(/[\\/]/).pop())).join(', ')||
        oldActive.map(v=>esc(v.original_filename)).join(', ')}.</span>
      <span>Стандарт: <code>${esc(standard)}</code>. Прежние Image ID сохраняются.</span>
      <span>Нажми на legacy-точку (или «Index existing weapon images») для подключения прежнего Image ID (без публикации),
        либо «Upload new atlas» для новой версии с предпросмотром и подтверждением замены.</span>
      </div>` : '';
    const empty = !bound && !(item.atlas_variants||[]).length && !virtual.length;
    host.innerHTML = `<div class="game1-atlas-header"><strong>Atlas resolutions</strong><small>Shared Atlas Registry · separate Studio Sync</small></div>`
      + (empty ? `<small class="game1-atlas-note">Нет подключённых градаций. Выбери «Connect existing atlas» или индексируй ранее опубликованный Image ID.</small>` : '')
      + legacyHtml
      + editor().render(state,options)
      + `<div class="game1-atlas-utilities"><button type="button" data-wa-clear ${bound?'':'disabled'}>Unbind</button><button type="button" data-wa-refresh>Refresh library</button></div>`;
    editor().wire(host,state,options);
    host.querySelector('[data-wa-clear]').onclick=async()=>{
      if(!confirm(`Unbind shared atlas from ${kind} ${item.slug}? Studio Sync is still required.`))return;
      try{
        await request('/api/texture-atlases/consumer-choice',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({consumerType:kind,slug:item.slug,action:'clear'})});
        await reload();
        toast('Atlas unbound. Sync Studio explicitly when ready.');
      }catch(error){toast(error.message,true);}
    };
    host.querySelector('[data-wa-refresh]').onclick=async()=>{
      try{await refresh();await reload();}catch(error){toast(error.message,true);}
    };
  }
  return Object.freeze({refresh,render,summary});
})();
