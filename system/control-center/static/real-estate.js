/* Real Estate registry view. Global request(), toast(), esc(), $ provided by Character Assets. */
const realEstateState = {data:null, selected:null, inspect:null, textures:{}, textureRefs:{}, reuseEnabled:{}, reuseFilters:{}, acceptWarnings:false, atlasBusy:false};
const REAL_ESTATE_SELECTED = 'game1.realEstate.selected';
let realEstatePublicationPoll = null;
function realEstatePublicationBusy(slug){
  const job=realEstateState.publicationJob;
  return Boolean(job && slug && job.slug===slug && (job.status==='queued'||job.status==='running'));
}
async function realEstateWatchPublication(slug, notify=false){
  if(!slug)return;
  if(realEstatePublicationPoll){clearTimeout(realEstatePublicationPoll);realEstatePublicationPoll=null;}
  const response=await request('/api/real-estate/'+encodeURIComponent(slug)+'/publication-job');
  const job=response?.job||null;
  realEstateState.publicationJob=job;
  realEstateRender();
  if(job && (job.status==='queued'||job.status==='running')){
    realEstatePublicationPoll=setTimeout(()=>realEstateWatchPublication(slug,true).catch(e=>toast(e.message,true)),2000);
  }else if(notify && job){
    if(job.status==='failed')toast(`Real Estate publish failed at ${job.step}: ${job.error}`,true);
    else if(job.status==='succeeded')toast(`${slug} · publication completed`);
    await realEstateLoad();
  }
}

function realEstateRows(){return (Array.isArray(realEstateState.data?.items)?realEstateState.data.items:[]).filter(item=>item&&typeof item.slug==='string');}
function realEstateSelected(){return realEstateRows().find(item=>item.slug===realEstateState.selected)||null;}
function realEstateStatus(){const row=realEstateSelected();return row?.status||'LOCAL_ONLY';}
function realEstateRemember(){try{localStorage.setItem(REAL_ESTATE_SELECTED,realEstateState.selected||'');}catch{}}
function realEstateForm(row){
  realEstateState.selected=row?.slug||null;
  realEstateRemember();
  realEstateState.inspect=null;
  realEstateState.acceptWarnings=Boolean(row);
  realEstateState.reuseFilters={};
  const meshNames=(row?.meshParts||[]);
  realEstateState.textureRefs=Object.fromEntries(
    meshNames.map(part=>[part,row?.textures?.[part]?.reuseReference||'']));
  realEstateState.reuseEnabled=Object.fromEntries(
    meshNames.map(part=>[part,Boolean(row?.textures?.[part]?.reuseReference)]));
  realEstateState.textures=Object.fromEntries(
    meshNames.map(part=>[part,row?.textures?.[part]?.reuseReference?'':(row?.textures?.[part]?.path||'')]));
  $('real-estate-fbx').textContent=row?`${row.model_path} · choose FBX to replace`:'no FBX selected';
  $('real-estate-type').value=row?.house_type||'house';
  $('real-estate-level').value=row?.house_level??1;
  $('real-estate-variant').value=row?.variant||'01';
  $('real-estate-purchase').value=row?.purchase_price??1;
  $('real-estate-min-level').value=row?.min_level??1;
  $('real-estate-sale').value=row?.sale_price??1;
  $('real-estate-description').value=`Game1 Real Estate ${row?.slug||'house'}`;
  realEstateRenderRigs(row?.skeleton||null, row?.rigWarnings||[]);
  realEstateRenderTextures(row);
  realEstateRender();
}
function realEstateRenderRigs(analysis, warnings=[]){
  const meshes=analysis?.meshes||[];
  const summary=$('real-estate-rig');
  summary.textContent=meshes.length
    ? meshes.map(part=>`${part.name}: ${part.bones?.length||0} bone(s)`).join(' · ')+' · view bones'
    : 'choose an FBX to view mesh / bone details';
  $('real-estate-bone-list').innerHTML=meshes.map(part=>{
    const bones=part.bones||[];
    return `<section class="real-estate-bone-group"><strong>${esc(part.name)} · ${esc(part.armature||'no armature')}</strong>
      ${bones.length?`<ul>${bones.map(b=>`<li><code>${esc(b.name)}</code>${b.parent?` <span class="muted">← ${esc(b.parent)}</span>`:''}</li>`).join('')}</ul>`:'<small class="muted">No bones · valid for publication</small>'}</section>`;
  }).join('');
  const warningBox=$('real-estate-rig-warnings');
  warningBox.hidden=!warnings.length;
  warningBox.innerHTML=warnings.length
    ? `<strong>FBX warnings (${warnings.length})</strong><ul>${warnings.map(w=>`<li>${esc(w.message)}</li>`).join('')}</ul><small>house and house_armature are required. Door and interaction bones are optional.</small>`
    : '';
}
function realEstateOptions(){
  const item=realEstateState.inspect;
  return item ? item.textures||[] : [];
}
// Catalog entries retain owner identity. Location categories come from the
// existing Location Asset registry; the selected item remains visible while
// the user filters, so filtering can never silently replace a saved reference.
function realEstateLocationCategories(){
  const entries=(realEstateState.data?.textureReferences||[]).filter(e=>e.group==='location'||e.reference.startsWith('location:'));
  const categories=new Map(entries.map(e=>[e.category||'other',e.categoryLabel||e.category||'Other']));
  return [...categories.entries()].sort((a,b)=>a[1].localeCompare(b[1]));
}
// Display identity and file metadata are deliberately separate from the
// stable reuse reference: changing how options look cannot change ownership.
function realEstateReuseLabel(entry){
  return [entry.label, entry.filename||String(entry.path||'').split(/[\\/]/).pop()||'unknown file', entry.assetId].join(' · ');
}
function realEstateLocalHouseAtlasLabel(){
  const owner=realEstateSelected()?.textures?.house||{};
  const current=realEstateState.textures.house||'';
  const source=(realEstateState.data?.textureReferences||[]).find(e=>e.reference===realEstateState.textureRefs.house);
  const filename=(source?.filename || (current && current!==owner.path?current.split(/[\\/]/).pop():'') ||
    owner.filename || current.split(/[\\/]/).pop() || String(owner.path||'').split(/[\\/]/).pop() || 'no texture selected');
  return ['this Estate / house', filename, source?.assetId||owner.assetId||'not published'].join(' · ');
}
function realEstateReuseOptions(part){
  const all=realEstateState.data?.textureReferences||[];
  const active=realEstateState.textureRefs[part]||'';
  const filter=realEstateState.reuseFilters[part]||{category:'',query:''};
  const query=(filter.query||'').trim().toLocaleLowerCase();
  const matching=e=>e.reference===active||(!query||
    [e.label,e.slug,e.filename,e.path,e.reference,e.categoryLabel,e.assetId].some(v=>String(v||'').toLocaleLowerCase().includes(query)));
  const location=all.filter(e=>(e.group==='location'||e.reference.startsWith('location:'))&&
    (e.reference===active||!filter.category||e.category===filter.category)&&matching(e));
  const estates=all.filter(e=>(e.group==='estate'||e.reference.startsWith('estate:'))&&matching(e));
  const option=e=>`<option value="${esc(e.reference)}">${esc(realEstateReuseLabel(e))}</option>`;
  const result=['<option value="">choose reuse source…</option>'];
  if(part!=='house')result.push(`<optgroup label="This Estate"><option value="mesh:house">${esc(realEstateLocalHouseAtlasLabel())}</option></optgroup>`);
  const categories=new Map();
  for(const e of location){
    const key=e.category||'other';
    if(!categories.has(key))categories.set(key,{label:e.categoryLabel||key,entries:[]});
    categories.get(key).entries.push(e);
  }
  for(const category of [...categories.values()].sort((a,b)=>a.label.localeCompare(b.label))){
    result.push(`<optgroup label="Location Assets · ${esc(category.label)}">${category.entries.map(option).join('')}</optgroup>`);
  }
  if(estates.length)result.push(`<optgroup label="Real Estate · registered">${estates.map(option).join('')}</optgroup>`);
  return result.join('');
}
function realEstateUpdateReuseOptions(part){
  const select=$(`real-estate-reference-${part}`);
  select.innerHTML=realEstateReuseOptions(part);
  select.value=realEstateState.textureRefs[part]||'';
}
function realEstateParts(){
  const analysis=realEstateState.inspect?.analysis||realEstateSelected()?.skeleton;
  return (analysis?.meshes||[]).map(mesh=>mesh.name).filter(name=>typeof name==='string');
}
function realEstateRenderTextures(){
  const host=$('real-estate-mesh-textures');
  const parts=realEstateParts();
  const options=realEstateOptions();
  const categories=realEstateLocationCategories();
  host.innerHTML=parts.map(part=>{
    let selected=realEstateState.textures[part]||'';
    const reuse=realEstateState.reuseEnabled[part]===true;
    if(!selected && !reuse){
      const guess=options.find(item=>item.name.toLowerCase().startsWith(part+'.')||item.name.toLowerCase().startsWith(part+'_'));
      if(guess)selected=guess.path;
    }
    realEstateState.textures[part]=selected;
    const choices=[`<option value="">choose texture…</option>`];
    if(selected && !options.some(item=>item.path===selected)){
      choices.push(`<option value="${esc(selected)}">${esc(selected.split(/[\\/]/).pop())} · selected</option>`);
    }
    for(const item of options)choices.push(`<option value="${esc(item.path)}">${esc(item.name)}</option>`);
    const filters=realEstateState.reuseFilters[part]||{category:'',query:''};
    realEstateState.reuseFilters[part]=filters;
    const categoryChoices=['<option value="">all Location categories</option>',
      ...categories.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`)];
    return `<div class="real-estate-texture-row" data-texture-part="${esc(part)}">
      <div class="real-estate-texture-heading"><strong>${esc(part)}</strong>
        <label class="real-estate-reuse-toggle"><input type="checkbox" id="real-estate-reuse-${esc(part)}" ${reuse?'checked':''}> reuse</label></div>
      <div id="real-estate-owned-${esc(part)}" class="real-estate-texture-owned" ${reuse?'hidden':''}>
        <select aria-label="${esc(part)} texture" id="real-estate-texture-${esc(part)}">${choices.join('')}</select>
        <button type="button" id="real-estate-browse-${esc(part)}">browse…</button>
        <small class="muted real-estate-texture-path" id="real-estate-texture-path-${esc(part)}" title="${esc(selected)}">${esc(selected||'no texture selected')}</small>
      </div>
      <div id="real-estate-shared-${esc(part)}" class="real-estate-texture-shared" ${reuse?'':'hidden'}>
        <div class="real-estate-reuse-filters">
          <input type="search" id="real-estate-reuse-search-${esc(part)}" aria-label="Search ${esc(part)} reuse" placeholder="search asset, filename, slug or ID…" value="${esc(filters.query)}">
          <select id="real-estate-reuse-category-${esc(part)}" aria-label="${esc(part)} Location category">${categoryChoices.join('')}</select>
        </div>
        <select aria-label="${esc(part)} reused texture" id="real-estate-reference-${esc(part)}"></select>
        <small class="hint">Published Location/Real Estate Image Asset · or atlas from this Estate</small>
      </div></div>`;
  }).join('');
  for(const part of parts){
    const select=$(`real-estate-texture-${part}`);
    select.value=realEstateState.textures[part];
    select.onchange=()=>{
      realEstateState.textures[part]=select.value;
      $(`real-estate-texture-path-${part}`).textContent=select.value||'no texture selected';
    };
    $(`real-estate-browse-${part}`).onclick=()=>realEstateBrowseTexture(part);
    const shared=$(`real-estate-reference-${part}`);
    const filters=realEstateState.reuseFilters[part];
    const category=$(`real-estate-reuse-category-${part}`);
    category.value=filters.category;
    const search=$(`real-estate-reuse-search-${part}`);
    search.oninput=()=>{filters.query=search.value;realEstateUpdateReuseOptions(part);};
    category.onchange=()=>{filters.category=category.value;realEstateUpdateReuseOptions(part);};
    realEstateUpdateReuseOptions(part);
    shared.onchange=()=>{realEstateState.textureRefs[part]=shared.value;};
    $(`real-estate-reuse-${part}`).onchange=(event)=>{
      const enabled=event.target.checked;
      realEstateState.reuseEnabled[part]=enabled;
      if(!enabled)realEstateState.textureRefs[part]='';
      $('real-estate-owned-'+part).hidden=enabled;
      $('real-estate-shared-'+part).hidden=!enabled;
      if(!enabled)shared.value='';
    };
  }
}

async function realEstateBrowseTexture(part){
  try{
    const initialPath=realEstateState.inspect?.sourcePath||'';
    const result=await request('/api/files/choose-real-estate-texture',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialPath})
    });
    if(!result.path)return false; // Cancel preserves the current selection.
    realEstateState.textures[part]=result.path;
    realEstateState.textureRefs[part]='';
    realEstateState.reuseEnabled[part]=false;
    realEstateRenderTextures();
    return true;
  }catch(error){toast(error.message,true);return false;}
}
function realEstateIdentity(){
  const kind=$('real-estate-type').value.trim().toLowerCase();
  const level=Number($('real-estate-level').value||1);
  const variant=$('real-estate-variant').value.trim();
  const slug=(kind&&Number.isInteger(level)&&level>0&&/^\d+$/.test(variant))?`${kind}_level${level}_${variant.padStart(2,'0')}`:'';
  $('real-estate-slug').textContent=slug||'invalid identity';
  if(!realEstateState.selected)$('real-estate-description').value=`Game1 Real Estate ${slug}`;
}
async function realEstateChooseFbx(){
  try {
    const result=await request('/api/files/choose-real-estate-model',{method:'POST'});
    if(!result.path)return false;
    const inspection=await request('/api/real-estate/inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sourcePath:result.path})});
    const warnings=inspection.warnings||[];
    if(warnings.length){
      const description=warnings.map(w=>`• ${w.message}`).join('\n');
      const accepted=window.confirm(`FBX inspection warnings:\n\n${description}\n\nContinue with this FBX?`);
      if(!accepted){
        toast('FBX selection cancelled · previous registration unchanged');
        return false;
      }
    }
    realEstateState.inspect=inspection;
    realEstateState.acceptWarnings=Boolean(warnings.length);
    $('real-estate-fbx').textContent=inspection.sourcePath;
    if(!realEstateState.selected){
      $('real-estate-type').value=inspection.houseType;
      $('real-estate-level').value=inspection.level;
      $('real-estate-variant').value=inspection.variant;
    }
    realEstateRenderRigs(inspection.analysis, warnings);
    // Existing mesh textures remain selected while FBX is replaced independently.
    if(!realEstateState.selected){
      realEstateState.textures={};realEstateState.textureRefs={};realEstateState.reuseEnabled={};
      // Every auxiliary mesh can reuse the selected local house atlas before
      // this Estate has any Image Asset ID. Respect explicitly named textures.
      for(const mesh of inspection.analysis?.meshes||[]){
        const part=mesh.name;
        if(part==='house')continue;
        const hasOwnTexture=(inspection.textures||[]).some(t=>t.name.toLowerCase().startsWith(part.toLowerCase()+'.')||t.name.toLowerCase().startsWith(part.toLowerCase()+'_'));
        if(!hasOwnTexture){realEstateState.textureRefs[part]='mesh:house';realEstateState.reuseEnabled[part]=true;}
      }
    }
    realEstateRenderTextures();
    realEstateIdentity();
    toast('FBX analyzed · choose WebP, PNG, JPG or JPEG for each mesh');
    return true;
  } catch(error) {toast(error.message,true);return false;}
}
function realEstatePayload(){
  const parts=realEstateParts();
  for(const part of parts){
    if(realEstateState.reuseEnabled[part] && !realEstateState.textureRefs[part]){
      throw Error(`choose a reusable texture source for ${part}`);
    }
  }
  const current=realEstateSelected();
  return {existingSlug:current?.slug||'', sourcePath:realEstateState.inspect?.sourcePath||'',
    houseType:$('real-estate-type').value,level:$('real-estate-level').value,
    variant:$('real-estate-variant').value,purchasePrice:$('real-estate-purchase').value,
    minLevel:$('real-estate-min-level').value,salePrice:$('real-estate-sale').value,
    textures:Object.fromEntries(parts.map(part=>[part,realEstateState.textureRefs[part]?'':(realEstateState.textures[part]||'')])),
    textureReferences:Object.fromEntries(parts.map(part=>[part,realEstateState.textureRefs[part]||''])),
    acceptWarnings:realEstateState.acceptWarnings};
}
async function realEstateRegister(){
  try{
    $('real-estate-register').disabled=true;
    const row=await request('/api/real-estate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(realEstatePayload())});
    realEstateState.selected=row.slug;
    await realEstateLoad();
    toast(`Real Estate registered · ${row.slug}`);
    return true;
  }catch(error){toast(error.message,true);return false;}finally{$('real-estate-register').disabled=false;}
}
async function realEstateSync(slug){
  const row=realEstateRows().find(item=>item.slug===slug);
  if(!row)return;
  try{
    toast('syncing '+slug+' to Studio ServerStorage…');
    const result=await request('/api/real-estate/'+encodeURIComponent(slug)+'/sync',{method:'POST'});
    const warnings=result.studio?.realEstateStats?.rigWarnings||[];
    toast(`Studio synced · ${result.studio?.destination||slug}${warnings.length?' · '+warnings.length+' optional bone warnings':''}`);
    if(warnings.length){
      const box=$('real-estate-rig-warnings');
      box.hidden=false;
      box.innerHTML=`<strong>Studio import warnings (${warnings.length})</strong><ul>${warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul><small>Sync succeeded. Missing optional bones will not be available for interactions; republish the affected rig only if needed.</small>`;
    }
  }catch(error){toast(error.message,true);}
}
async function realEstatePublish(scope='all'){
  const row=realEstateSelected(); if(!row)return;
  const button=$('real-estate-publish');
  try{
    button.disabled=true;
    toast(`publishing changed ${scope==='all'?'Real Estate assets':scope} for ${row.slug}…`);
    const result=await request('/api/real-estate/'+encodeURIComponent(row.slug)+'/publish-async',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({description:$('real-estate-description').value,scope})});
    realEstateState.publicationJob=result.job;
    realEstateRender();
    await realEstateWatchPublication(row.slug,true);
    return result;
  }catch(error){toast(error.message,true);return null;}finally{
    button.disabled=!realEstateSelected()||!realEstateState.data?.publication?.configured||realEstateStatus()==='PUBLISHED'||realEstatePublicationBusy(realEstateState.selected);
  }
}
async function realEstateReplaceFbx(row){
  realEstateForm(row);
  if(await realEstateChooseFbx())await realEstateRegister();
}
async function realEstateReplaceTexture(row,part){
  realEstateForm(row);
  if(await realEstateBrowseTexture(part))await realEstateRegister();
}
// Central Atlas Registry presentation; one independent binding per Estate mesh.
// Colors are relative ranks, never absolute resolution thresholds.
const REAL_ESTATE_ATLAS_COLORS = ['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'];
function realEstateAtlasDots(texture, part){
  const variants=[...(texture?.atlasVariants||[])].sort((a,b)=>(Number(b.width)*Number(b.height)-Number(a.width)*Number(a.height))||Number(b.width)-Number(a.width)||Number(b.height)-Number(a.height));
  if(!variants.length)return '';
  const dots=variants.map((variant,index)=>{
    const active=Number(texture.atlasVariantId)===Number(variant.id);
    const name=variant.filename||`${variant.atlas_key}_${variant.resolution}_atlas.png`;
    const hint=`${variant.resolution} · ${name}${variant.current?'':' · publish first'}`;
    return `<button type="button" class="deco-atlas-dot ${active?'is-active':''}" style="--dot-color:${REAL_ESTATE_ATLAS_COLORS[Math.min(index,4)]}" data-re-atlas-part="${esc(part)}" data-re-atlas-id="${Number(variant.id)}" title="${esc(hint)}" aria-label="${esc(hint)}" aria-pressed="${active}" ${(!variant.current||realEstateState.atlasBusy)?'disabled':''}><span></span></button>`;
  });
  return `<div class="deco-atlas-dots real-estate-atlas-dots" aria-label="Registered atlas resolutions">${dots.slice(0,5).join('')}${dots.length>5?`<details class="deco-atlas-more"><summary>+${dots.length-5}</summary><div>${dots.slice(5).join('')}</div></details>`:''}</div>`;
}
async function realEstateChooseAtlas(row,part,variantId){
  const texture=row.textures?.[part];
  if(!texture||realEstateState.atlasBusy||Number(texture.atlasVariantId)===Number(variantId))return;
  realEstateState.atlasBusy=true;
  realEstateRender();
  try{
    const result=await request(`/api/real-estate/${encodeURIComponent(row.slug)}/atlas-binding`,{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({part,variantId,expectedRevision:texture.reuseReference?0:Number(texture.atlasBindingRevision||0)})
    });
    await realEstateLoad();
    if(result.studioSyncStatus==='pending_studio_sync'){
      toast(`Atlas selected · Studio sync pending: ${result.studioError||'Studio unavailable'}`,true);
    }else toast(`${row.slug} / ${part} · atlas changed and Studio synced`);
  }catch(error){toast(`Atlas change: ${error.message}`,true);await realEstateLoad();}
  finally{realEstateState.atlasBusy=false;realEstateRender();}
}
function realEstateRender(){
  const rows=realEstateRows();
  $('real-estate-count').textContent=rows.length;
  $('real-estate-library-count').textContent=rows.length;
  $('real-estate-tree').innerHTML=rows.map(item=>`<button type="button" data-real-estate="${esc(item.slug)}" class="${item.slug===realEstateState.selected?'active':''}">${esc(item.slug)} · ${esc(item.status)}</button>`).join('')||'<span class="muted">No houses registered.</span>';
  for(const node of $('real-estate-tree').querySelectorAll('[data-real-estate]'))node.onclick=()=>realEstateForm(rows.find(row=>row.slug===node.dataset.realEstate));
  const tbody=$('real-estate-library-rows');
  tbody.innerHTML=rows.map(item=>{
    const textures=item.textures||{};
    const rigs=item.rigAssets||{};
    const live=item.publicationCurrent||{};
    const parts=item.meshParts||[];
    const canPublish=Boolean(realEstateState.data?.publication?.configured);
    const isBusy=realEstatePublicationBusy(item.slug);
    const asset=(id,ready)=>id?`${esc(id)}${ready?'':' · changed'}`:'not published';
    const textureLines=parts.map(part=>{
      const tex=textures[part]||{};
      const filename=tex.filename||tex.path?.split('/').pop()||tex.reuseReference||'—';
      return `<div class="real-estate-texture-line"><strong>${esc(part)}</strong>: <span class="real-estate-texture-filename">${esc(filename)}</span>${tex.atlasLegacyWarning?'<span class="deco-atlas-warning" title="Expected &lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png"> ⚠️</span>':''}${realEstateAtlasDots(tex,part)}${tex.atlasSyncStatus==='pending_studio_sync'?'<button type="button" data-re-atlas-retry="'+esc(part)+'" class="deco-atlas-retry">Sync pending · retry</button>':''}</div>`;
    }).join('');
    const assetLines=parts.map(part=>`<div class="real-estate-asset-part">
      <strong class="real-estate-asset-part-name">${esc(part)}</strong>
      <div class="real-estate-asset-identities">
        <span class="real-estate-asset-id real-estate-asset-model"><span>model</span><code>${asset(rigs[part]?.assetId,live.model)}</code></span>
        <span class="real-estate-asset-id real-estate-asset-image"><span>image</span><code>${asset(textures[part]?.assetId,live[part])}</code></span>
      </div></div>`).join('');
    const controls=parts.map(part=>{
      const shared=Boolean(textures[part]?.reuseReference);
      return `<button type="button" data-re-texture="${esc(part)}">${esc(part)} texture</button>`+
        `<button type="button" data-re-image="${esc(part)}" ${!canPublish||isBusy||live[part]||shared?'disabled':''}>${shared?'reused · '+esc(part):'publish '+esc(part)+' image'}</button>`+
        `<button type="button" data-re-rig="${esc(part)}" ${!canPublish||isBusy?'disabled':''}>republish ${esc(part)} rig</button>`;
    }).join('');
    return `<tr class="${item.slug===realEstateState.selected?'active':''}" data-house="${esc(item.slug)}"><td><b>${esc(item.slug)}</b><br><small>level ${esc(item.house_level)} · variant ${esc(item.variant)}</small></td><td><small>buy ${esc(item.purchase_price)} · sell ${esc(item.sale_price)}<br>level required ${esc(item.min_level)}</small></td><td><small>${textureLines}</small></td><td class="real-estate-assets-cell">${assetLines}</td><td><div class="real-estate-row-actions"><button type="button" data-re-edit>edit</button><button type="button" data-re-fbx>replace FBX</button>${controls}<button type="button" data-re-pub-model ${!canPublish||isBusy||live.model?'disabled':''}>publish FBX</button><button type="button" data-re-publish ${!canPublish||isBusy||item.status==='PUBLISHED'?'disabled':''}>publish changed</button><button type="button" data-re-sync ${isBusy||item.status!=='PUBLISHED'?'disabled':''}>sync Studio</button></div></td></tr>`;
  }).join('')||'<tr><td colspan="5" class="muted">No registered houses yet.</td></tr>';
  for(const tr of tbody.querySelectorAll('[data-house]')){
    const row=rows.find(item=>item.slug===tr.dataset.house);
    tr.querySelector('[data-re-edit]').onclick=()=>realEstateForm(row);
    tr.querySelector('[data-re-fbx]').onclick=()=>realEstateReplaceFbx(row);
    for(const button of tr.querySelectorAll('[data-re-texture]')){
      button.onclick=()=>realEstateReplaceTexture(row,button.dataset.reTexture);
    }
    for(const button of tr.querySelectorAll('[data-re-image]')){
      button.onclick=async()=>{realEstateForm(row);await realEstatePublish('image:'+button.dataset.reImage);};
    }
    for(const button of tr.querySelectorAll('[data-re-rig]')){
      button.onclick=async()=>{
        const part=button.dataset.reRig;
        if(!window.confirm(`Republish ${row.slug} / ${part} rig as a NEW Model Asset ID? The existing ID will remain until publication succeeds. Images and other rigs will not be republished.`))return;
        realEstateForm(row);
        await realEstatePublish('model:'+part);
      };
    }
    tr.querySelector('[data-re-pub-model]').onclick=async()=>{realEstateForm(row);await realEstatePublish('model');};
    tr.querySelector('[data-re-publish]').onclick=async()=>{realEstateForm(row);await realEstatePublish('all');};
    tr.querySelector('[data-re-sync]').onclick=()=>realEstateSync(row.slug);
    for(const button of tr.querySelectorAll('[data-re-atlas-id]')){
      button.onclick=()=>realEstateChooseAtlas(row,button.dataset.reAtlasPart,Number(button.dataset.reAtlasId));
    }
    for(const button of tr.querySelectorAll('[data-re-atlas-retry]')){
      button.onclick=()=>realEstateSync(row.slug).then(()=>realEstateLoad());
    }
  }
  const row=realEstateSelected();
  const busy=row&&realEstatePublicationBusy(row.slug);
  $('real-estate-publish').disabled=!row||!realEstateState.data?.publication?.configured||row.status==='PUBLISHED'||busy;
  $('real-estate-sync').disabled=!row||row.status!=='PUBLISHED'||busy;
  const job=realEstateState.publicationJob;
  $('real-estate-publish-status').textContent=busy
    ? `Publishing ${job.scope} · ${job.step} (continues in Host Agent if this tab closes)`
    : job?.slug===row?.slug&&job.status==='failed'
      ? `Last publication failed · ${job.step}: ${job.error}`
      : row?`${row.status} · ${(row.meshParts||[]).map(p=>p.slice(0,1).toUpperCase()+p.slice(1)+'Rig').join(' + ')} ${row.publicationCurrent?.model?'ready':'changed'} · ${row.meshParts?.map(part=>`${part} image ${row.publicationCurrent?.[part]?'ready':'changed'}`).join(' · ')} · Sync Studio requires all present assets ready`:'register a house first';
  realEstateIdentity();
}
async function realEstateLoad(){
  try{
    const snapshot=await request('/api/real-estate');
    if(!snapshot||!Array.isArray(snapshot.items)){throw Error('Real Estate API returned no registered-houses list. Reload Control Center.');}
    realEstateState.data=snapshot;
    if(!realEstateState.selected){try{realEstateState.selected=localStorage.getItem(REAL_ESTATE_SELECTED)||null;}catch{}}
    if(realEstateState.selected && !realEstateSelected())realEstateState.selected=null;
    realEstateForm(realEstateSelected());
    if(realEstateState.selected)await realEstateWatchPublication(realEstateState.selected,false);
  }catch(error){toast(error.message,true);}
}
window.game1RealEstateLoad=realEstateLoad;
$('real-estate-new').onclick=()=>realEstateForm(null);
$('real-estate-refresh').onclick=realEstateLoad;
$('real-estate-choose').onclick=realEstateChooseFbx;
$('real-estate-register').onclick=realEstateRegister;
$('real-estate-publish').onclick=()=>realEstatePublish('all');
$('real-estate-sync').onclick=()=>realEstateSync(realEstateState.selected);
$('real-estate-library-refresh').onclick=realEstateLoad;
for(const id of ['real-estate-type','real-estate-level','real-estate-variant'])$(id).addEventListener('input',realEstateIdentity);

if (!$('real-estate-view').hidden) realEstateLoad();
