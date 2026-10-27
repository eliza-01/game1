/* Real Estate registry view. Global request(), toast(), esc(), $ provided by Character Assets. */
const realEstateState = {data:null, selected:null, inspect:null, textures:{}, textureRefs:{}, reuseEnabled:{}, reuseFilters:{}, meshOptions:{}, atlasHouse:'', atlasMode:'all', acceptWarnings:false, atlasBusy:false};
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
function realEstateMeshLabel(part){return part==='repair'?'restoration (legacy: repair)':part;}
// Shared naming contract: COL_Floor / house_col / wall_COL_01 are physics-only.
function realEstateIsCollider(part){return /(?:^|_)col(?:_|$)/i.test(part);}
function realEstateMeshDefaults(part){return {glass:part.toLowerCase().includes('glass')&&!realEstateIsCollider(part),noCollide:!realEstateIsCollider(part)};}
function realEstateRemember(){try{localStorage.setItem(REAL_ESTATE_SELECTED,realEstateState.selected||'');}catch{}}
function realEstateForm(row){
  realEstateState.selected=row?.slug||null;
  realEstateRemember();
  realEstateState.inspect=null;
  realEstateState.acceptWarnings=Boolean(row);
  realEstateState.reuseFilters={};
  const meshNames=(row?.meshParts||[]);
  realEstateState.meshOptions=Object.fromEntries(meshNames.map(part=>[part,{
    glass:row?.meshOptions?.[part]?.glass ?? realEstateMeshDefaults(part).glass,
    noCollide:row?.meshOptions?.[part]?.noCollide ?? realEstateMeshDefaults(part).noCollide
  }]));
  // A central AtlasRegistry binding is reuse even when the legacy Estate
  // texture row has reuseReference="". The binding, not the local source path,
  // determines the active published Image Asset ID.
  const referenceForPart=part=>{
    const texture=row?.textures?.[part]||{};
    if(texture.reuseReference)return texture.reuseReference;
    return texture.atlasVariantId && texture.atlasCurrent
      ? `atlas:${texture.atlasVariantId}` : '';
  };
  realEstateState.textureRefs=Object.fromEntries(
    meshNames.map(part=>[part,referenceForPart(part)]));
  realEstateState.reuseEnabled=Object.fromEntries(
    meshNames.map(part=>[part,Boolean(referenceForPart(part))]));
  realEstateState.textures=Object.fromEntries(
    meshNames.map(part=>[part,referenceForPart(part)?'':(row?.textures?.[part]?.path||'')]));
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
// Render roles from authored bone names, never guess rig ownership from a name.
function realEstateBoneRole(part, name){
  if(part==='door' && name==='door_01_hinge_socket')return 'hinge';
  if(name.endsWith('_socket'))return 'socket';
  return 'bone';
}
function realEstateRigMode(part){
  const names=new Set((part.bones||[]).map(b=>b.name));
  if(part.name==='door')return names.has('door_01_hinge_socket')
    ? 'Hinge · rigid assembly pivot' : 'Legacy · no hinge pivot';
  if(part.name==='house')return `${[...names].filter(n=>n.endsWith('_socket')).length} authored sockets`;
  return part.armature?'Independent rig':'Static mesh';
}
function realEstateRenderRigs(analysis, warnings=[]){
  const meshes=analysis?.meshes||[];
  const summary=$('real-estate-rig');
  summary.textContent=meshes.length
    ? meshes.map(part=>`${realEstateMeshLabel(part.name)}: ${part.bones?.length||0} bones`).join(' · ')+' · view rig roles'
    : 'choose an FBX to view mesh / bone details';
  $('real-estate-bone-list').innerHTML=meshes.map(part=>{
    const bones=part.bones||[];
    const mode=realEstateRigMode(part);
    return `<section class="real-estate-bone-group"><strong>${esc(realEstateMeshLabel(part.name))} · ${esc(part.armature||'no linked armature')}</strong>
      <small class="real-estate-rig-mode">${esc(mode)}</small>
      ${bones.length?`<ul>${bones.map(b=>{
        const role=realEstateBoneRole(part.name,b.name);
        return `<li><code>${esc(b.name)}</code><span class="real-estate-bone-role">${role}</span>${b.parent?` <span class="muted">← ${esc(b.parent)}</span>`:''}</li>`;
      }).join('')}</ul>`:'<small class="muted">No authored bones · unrigged mesh</small>'}</section>`;
  }).join('');
  const warningBox=$('real-estate-rig-warnings');
  warningBox.hidden=!warnings.length;
  warningBox.innerHTML=warnings.length
    ? `<strong>FBX warnings (${warnings.length})</strong><ul>${warnings.map(w=>`<li>${esc(w.message)}</li>`).join('')}</ul><small>Only mesh house and its linked house_armature are mandatory. A hinge door must keep its socket hierarchy; older doors remain supported.</small>`
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
// The Atlas Registry catalog is authoritative for published atlas variants.
// textureReferences is a convenience projection that may omit modern atlases
// in an older Host Agent response; never make the reuse picker depend on it.
function realEstatePublishedAtlasChoices(){
  const choices=new Map();
  for(const entry of realEstateState.data?.textureReferences||[]){
    if((entry.group==='atlas'||String(entry.reference||'').startsWith('atlas:')) && entry.assetId){
      choices.set(entry.reference,entry);
    }
  }
  for(const family of realEstateState.data?.atlasCatalog||[]){
    for(const variant of family.variants||[]){
      if(!variant.current||!variant.published_id)continue;
      const reference=`atlas:${variant.id}`;
      choices.set(reference,{
        reference,group:'atlas',label:family.atlasKey,slug:'',
        filename:variant.filename,path:variant.source_path,
        assetId:String(variant.published_id),category:'',categoryLabel:''
      });
    }
  }
  return [...choices.values()].sort((a,b)=>
    String(a.label||'').localeCompare(String(b.label||'')) ||
    String(a.filename||'').localeCompare(String(b.filename||'')));
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
  // AtlasRegistry is the canonical owner of new Location/Real Estate atlases.
  // Do not infer ownership from an Estate row: a shared atlas may have no
  // legacy per-mesh image publication at all (e.g. house_level4_01).
  const atlases=realEstatePublishedAtlasChoices().filter(matching);
  const option=e=>`<option value="${esc(e.reference)}">${esc(realEstateReuseLabel(e))}</option>`;
  const result=['<option value="">choose reuse source…</option>'];
  if(part!=='house')result.push(`<optgroup label="This Estate"><option value="mesh:house">${esc(realEstateLocalHouseAtlasLabel())}</option></optgroup>`);
  // Show modern shared atlases before the long legacy owner lists.
  if(atlases.length)result.push(`<optgroup label="Shared Atlas Registry · published">${atlases.map(option).join('')}</optgroup>`);
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
  for(const part of parts){
    if(!realEstateState.meshOptions[part]||typeof realEstateState.meshOptions[part]!=='object'){
      realEstateState.meshOptions[part]=realEstateMeshDefaults(part);
    }
  }
  const options=realEstateOptions();
  const categories=realEstateLocationCategories();
  host.innerHTML=(parts.length&&!parts.some(realEstateIsCollider)
    ? '<small class="real-estate-physics-caution">No COL_ collision mesh in this FBX. If all visual meshes have No Collide enabled, characters will fall through the house until a collision model is published.</small>' : '')+parts.map(part=>{
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
    const collider=realEstateIsCollider(part);
    const flags=realEstateState.meshOptions[part];
    if(collider){
      return `<div class="real-estate-texture-row real-estate-collider-row" data-texture-part="${esc(part)}">
        <div class="real-estate-texture-heading"><strong class="real-estate-mesh-name">${esc(realEstateMeshLabel(part))}</strong><span class="real-estate-physics-badge">Collision · no texture</span></div>
        <div class="real-estate-mesh-switches" role="group" aria-label="${esc(part)} physics settings">
          <label class="real-estate-physics-toggle" title="Disable collisions and spatial queries for this mesh"><input type="checkbox" id="real-estate-nocollide-${esc(part)}" ${flags.noCollide?'checked':''}> No Collide</label>
        </div>
        <small class="real-estate-collider-note">Invisible in Studio · collidable by default · CanQuery on · CanTouch off. Use simple geometry even for a combined collider.</small></div>`;
    }
    return `<div class="real-estate-texture-row" data-texture-part="${esc(part)}">
      <div class="real-estate-texture-heading"><strong class="real-estate-mesh-name">${esc(realEstateMeshLabel(part))}</strong><span class="real-estate-mesh-kind">Visual mesh</span></div>
      <div class="real-estate-mesh-switches" role="group" aria-label="${esc(part)} mesh settings">
        <label class="real-estate-glass-toggle" title="Studio MeshPart Transparency = 0.02 (if checked)"><input type="checkbox" id="real-estate-glass-${esc(part)}" ${flags.glass?'checked':''}> Glass · 0.02</label>
        <label class="real-estate-physics-toggle" title="Disable physics collisions, touch events, and spatial queries for this mesh"><input type="checkbox" id="real-estate-nocollide-${esc(part)}" ${flags.noCollide?'checked':''}> No Collide</label>
        <label class="real-estate-reuse-toggle" title="Bind this mesh to an existing published Atlas Registry variant. Reuse never uploads another Roblox Image Asset."><input type="checkbox" id="real-estate-reuse-${esc(part)}" ${reuse?'checked':''}> Reuse atlas</label>
      </div>
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
        <small class="hint">Published Location/Real Estate Image Asset · Shared Atlas Registry (existing Roblox ID, no upload). For changed pixels, use Republish instead.</small>
      </div></div>`;
  }).join('');
  for(const part of parts){
    $(`real-estate-nocollide-${part}`).onchange=event=>{
      realEstateState.meshOptions[part].noCollide=event.target.checked;
    };
    if(realEstateIsCollider(part))continue;
    $(`real-estate-glass-${part}`).onchange=event=>{
      realEstateState.meshOptions[part].glass=event.target.checked;
    };
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
      realEstateState.textures={};realEstateState.textureRefs={};realEstateState.reuseEnabled={};realEstateState.meshOptions={};
      // Every auxiliary mesh can reuse the selected local house atlas before
      // this Estate has any Image Asset ID. Respect explicitly named textures.
      for(const mesh of inspection.analysis?.meshes||[]){
        const part=mesh.name;
        if(part==='house'||realEstateIsCollider(part))continue;
        const hasOwnTexture=(inspection.textures||[]).some(t=>t.name.toLowerCase().startsWith(part.toLowerCase()+'.')||t.name.toLowerCase().startsWith(part.toLowerCase()+'_'));
        if(!hasOwnTexture){realEstateState.textureRefs[part]='mesh:house';realEstateState.reuseEnabled[part]=true;}
      }
    }
    realEstateRenderTextures();
    realEstateIdentity();
    toast('FBX analyzed · visual meshes need textures; COL_ meshes are geometry-only');
    return true;
  } catch(error) {toast(error.message,true);return false;}
}
function realEstatePayload(){
  const parts=realEstateParts();
  for(const part of parts){
    if(realEstateIsCollider(part))continue;
    if(realEstateState.reuseEnabled[part] && !realEstateState.textureRefs[part]){
      throw Error(`choose a reusable texture source for ${part}`);
    }
  }
  const current=realEstateSelected();
  return {existingSlug:current?.slug||'', sourcePath:realEstateState.inspect?.sourcePath||'',
    houseType:$('real-estate-type').value,level:$('real-estate-level').value,
    variant:$('real-estate-variant').value,purchasePrice:$('real-estate-purchase').value,
    minLevel:$('real-estate-min-level').value,salePrice:$('real-estate-sale').value,
    textures:Object.fromEntries(parts.filter(part=>!realEstateIsCollider(part)).map(part=>[part,realEstateState.textureRefs[part]?'':(realEstateState.textures[part]||'')])),
    textureReferences:Object.fromEntries(parts.filter(part=>!realEstateIsCollider(part)).map(part=>[part,realEstateState.textureRefs[part]||''])),
    meshOptions:Object.fromEntries(parts.map(part=>[part,{
      glass:Boolean(realEstateState.meshOptions[part]?.glass),
      noCollide:Boolean(realEstateState.meshOptions[part]?.noCollide)
    }])),
    acceptWarnings:realEstateState.acceptWarnings};
}
async function realEstateRegister(){
  try{
    $('real-estate-register').disabled=true;
    const row=await request('/api/real-estate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(realEstatePayload())});
    realEstateState.selected=row.slug;
    await realEstateLoad();
    if(row.studioSyncStatus==='pending_studio_sync')toast(`Mesh settings saved · Studio Sync pending: ${row.studioError||'Studio unavailable'}`,true);
    else toast(`Real Estate registered · ${row.slug}${row.studioSyncStatus==='synced'?' · Studio updated':''}`);
    return true;
  }catch(error){toast(error.message,true);return false;}finally{$('real-estate-register').disabled=false;}
}
async function realEstateSync(slug){
  const row=realEstateRows().find(item=>item.slug===slug);
  if(!row)return;
  try{
    toast('syncing '+slug+' to Studio ServerStorage…');
    const result=await request('/api/real-estate/'+encodeURIComponent(slug)+'/sync',{method:'POST'});
    const stats=result.studio?.realEstateStats||{};
    const warnings=stats.rigWarnings||[];
    const missing=stats.missingSockets||[];
    const recovered=stats.recoveredSockets||[];
    if(missing.length){
      toast(`Studio template created · ${missing.length} socket(s) unavailable${recovered.length?' · '+recovered.length+' recovered from FBX':''}`,true);
    }else if(recovered.length){
      toast(`Studio synced · ${recovered.length} unweighted socket(s) recovered from authored FBX transforms`);
    }else{
      toast(`Studio synced · ${result.studio?.destination||slug}${warnings.length?' · '+warnings.length+' rig warnings':''}`);
    }
    if(warnings.length){
      const box=$('real-estate-rig-warnings');
      box.hidden=false;
      box.innerHTML=`<strong>Studio import warnings (${warnings.length})</strong><ul>${warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul><small>Template loaded. Only sockets with an imported parent Bone and a registered FBX rest transform can be recovered safely. Missing anchors remain unavailable; check the rig before enabling those interactions.</small>`;
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
async function realEstateDelete(row){
  if(realEstatePublicationBusy(row.slug)){toast('Wait for the publication to finish before deleting',true);return;}
  const message=`Remove ${row.slug} from the Real Estate registry?\n\nLocal FBX/texture files and published Roblox IDs will NOT be deleted. The database row and publication history are archived. Managed templates already in Studio will NOT be removed automatically. Houses reusing this house's texture will block deletion.`;
  if(!window.confirm(message))return;
  try{
    const result=await request('/api/real-estate/'+encodeURIComponent(row.slug),{method:'DELETE'});
    if(realEstateState.selected===row.slug){realEstateState.selected=null;realEstateRemember();}
    await realEstateLoad();
    toast(`House retired · archive ${result.archived} · Studio templates unchanged`);
  }catch(error){toast(`Cannot delete ${row.slug}: ${error.message}`,true);}
}
async function realEstateRepublishAtlas(variant){
  if(realEstateState.atlasBusy)return;
  const name=variant.filename||variant.atlas_key+'_'+variant.resolution+'_atlas.png';
  try{
    const file=await request('/api/files/choose-real-estate-texture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialPath:''})});
    if(!file?.path)return;
    if(!window.confirm(`Republish ${name} from ${file.path}?\n\nRoblox will assign a NEW Image Asset ID. All consumers of this atlas variant (including Location Assets) will switch to the new ID after successful publication.`))return;
    realEstateState.atlasBusy=true;
    realEstateRender();
    const result=await request('/api/texture-atlases/variants/'+Number(variant.id)+'/republish',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sourcePath:file.path})});
    await realEstateLoad();
    const errors=result.studioErrors||[];
    toast(result.unchanged?`Atlas bytes unchanged · no upload: ${name}`:
      `Atlas republished · new Roblox Image ID ${result.variant?.published_id||'—'}${errors.length?' · Studio Sync pending: '+errors.join('; '):''}`,Boolean(errors.length));
  }catch(error){toast('Atlas republish: '+error.message,true);}
  finally{realEstateState.atlasBusy=false;realEstateRender();}
}
async function realEstateRepublishLegacy(ownerSlug,part){
  const row=realEstateRows().find(item=>item.slug===ownerSlug);
  if(!row){toast('The owning house is no longer registered',true);return;}
  if(realEstatePublicationBusy(ownerSlug)){toast('Wait for this house publication',true);return;}
  if(!window.confirm(`Replace and republish the legacy atlas of ${ownerSlug} / ${part}?\n\nChoose the replacement texture. A successful upload creates a NEW Roblox Image Asset ID. This flow changes only the owning mesh. Other consumers still resolve their reuse reference.`))return;
  realEstateForm(row);
  if(!await realEstateBrowseTexture(part))return;
  if(!await realEstateRegister())return;
  await realEstatePublish('image:'+part);
}
function realEstateRenderAtlasLibrary(rows){
  const houseSelect=$('real-estate-atlas-house');
  const modeSelect=$('real-estate-atlas-mode');
  if(!houseSelect||!modeSelect)return;
  if(realEstateState.atlasHouse&&!rows.some(r=>r.slug===realEstateState.atlasHouse))realEstateState.atlasHouse='';
  houseSelect.innerHTML='<option value="">all houses</option>'+rows.map(r=>`<option value="${esc(r.slug)}">${esc(r.slug)}</option>`).join('');
  houseSelect.value=realEstateState.atlasHouse;
  modeSelect.value=realEstateState.atlasMode;
  const row=rows.find(r=>r.slug===realEstateState.atlasHouse);
  const used=new Set(Object.values(row?.textures||{}).map(t=>Number(t.atlasVariantId)).filter(Boolean));
  const catalog=realEstateState.data?.atlasCatalog||[];
  const variants=[];
  for(const family of catalog){
    for(const variant of family.variants||[]){
      const isUsed=used.has(Number(variant.id));
      const related=Boolean(row&&(family.atlasKey===row.slug||family.atlasKey.startsWith(row.slug+'_')));
      if(row&&realEstateState.atlasMode==='used'&&!isUsed)continue;
      if(row&&realEstateState.atlasMode==='related'&&!isUsed&&!related)continue;
      variants.push({...variant,atlasKey:family.atlasKey,isUsed});
    }
  }
  variants.sort((a,b)=>a.atlasKey.localeCompare(b.atlasKey)||Number(b.width)*Number(b.height)-Number(a.width)*Number(a.height));
  // Older Real Estate Image Assets may not have a parseable atlas name or
  // Atlas Variant ID. Surface these as legacy publications, never invent a
  // canonical family/variant for them or silently republish on selection.
  const legacyMap=new Map();
  for(const estate of rows){
    for(const [part,tex] of Object.entries(estate.textures||{})){
      if(realEstateIsCollider(part)||!tex.assetId||tex.atlasVariantId)continue;
      const key=String(tex.assetId);
      const entry=legacyMap.get(key)||{id:key,filename:tex.filename||tex.path?.split('/').pop()||'',owners:[],users:[]};
      entry.users.push(estate.slug+' / '+part);
      if(!tex.reuseReference)entry.owners.push({slug:estate.slug,part});
      legacyMap.set(key,entry);
    }
  }
  const legacy=[...legacyMap.values()].filter(item=>{
    if(!row||realEstateState.atlasMode==='all')return true;
    if(realEstateState.atlasMode==='used')return item.users.some(name=>name.startsWith(row.slug+' / '));
    return item.users.some(name=>name.startsWith(row.slug+' / ')) ||
      item.owners.some(owner=>owner.slug===row.slug);
  });
  const tbody=$('real-estate-atlas-rows');
  tbody.innerHTML=variants.map(v=>{
    const consumers=rows.flatMap(r=>Object.entries(r.textures||{}).filter(([,t])=>Number(t.atlasVariantId)===Number(v.id)).map(([part])=>r.slug+' / '+part));
    const hint=consumers.length?consumers.join(', '):'No current Real Estate consumers';
    return `<tr><td><strong>${esc(v.atlasKey)}</strong><br><small>${esc(v.filename||'')}</small></td><td>${esc(v.resolution||'')}</td><td><code>${esc(v.published_id||'not published')}</code></td><td><small title="${esc(hint)}">${esc(hint)}</small></td><td><button type="button" data-re-atlas-republish="${Number(v.id)}" ${!v.current||realEstateState.atlasBusy||!realEstateState.data?.publication?.configured?'disabled':''}>Republish · new ID</button></td></tr>`;
  }).join('')+legacy.map(item=>{
    const owner=item.owners[0];
    return `<tr class="real-estate-atlas-legacy"><td><strong>⚠️ legacy</strong><br><small>${esc(item.filename)}</small></td><td>unknown</td><td><code>${esc(item.id)}</code></td><td><small>${esc(item.users.join(', '))}</small></td><td>${owner?`<button type="button" data-re-legacy-slug="${esc(owner.slug)}" data-re-legacy-part="${esc(owner.part)}" ${realEstateState.atlasBusy||!realEstateState.data?.publication?.configured?'disabled':''}>Replace / republish · new ID</button>`:'<small>Owner not available</small>'}</td></tr>`;
  }).join('')||'<tr><td colspan="5" class="muted">No registered atlases match the filter.</td></tr>';
  $('real-estate-atlas-count').textContent=String(variants.length+legacy.length);
  for(const btn of tbody.querySelectorAll('[data-re-atlas-republish]')){
    const variant=variants.find(v=>Number(v.id)===Number(btn.dataset.reAtlasRepublish));
    btn.onclick=()=>realEstateRepublishAtlas(variant);
  }
  for(const btn of tbody.querySelectorAll('[data-re-legacy-slug]')){
    btn.onclick=()=>realEstateRepublishLegacy(btn.dataset.reLegacySlug,btn.dataset.reLegacyPart);
  }
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
      if(realEstateIsCollider(part))return `<div class="real-estate-texture-line"><strong>${esc(part)}</strong>: <span class="real-estate-physics-badge">physics only · no image</span></div>`;
      return `<div class="real-estate-texture-line"><strong>${esc(realEstateMeshLabel(part))}</strong>: <span class="real-estate-texture-filename">${esc(filename)}</span>${tex.atlasLegacyWarning?'<span class="deco-atlas-warning" title="Expected &lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png"> ⚠️</span>':''}${realEstateAtlasDots(tex,part)}${tex.atlasSyncStatus==='pending_studio_sync'?'<button type="button" data-re-atlas-retry="'+esc(part)+'" class="deco-atlas-retry">Sync pending · retry</button>':''}</div>`;
    }).join('');
    const assetLines=parts.map(part=>`<div class="real-estate-asset-part">
      <strong class="real-estate-asset-part-name">${esc(realEstateMeshLabel(part))}</strong>
      <div class="real-estate-asset-identities">
        <span class="real-estate-asset-id real-estate-asset-model"><span>model</span><code>${asset(rigs[part]?.assetId,live.model)}</code></span>
        ${realEstateIsCollider(part)?'<span class="real-estate-physics-badge">collision geometry</span>':`<span class="real-estate-asset-id real-estate-asset-image"><span>image</span><code>${asset(textures[part]?.assetId,live[part])}</code></span>`}
      </div></div>`).join('');
    const controls=parts.map(part=>{
      const shared=Boolean(textures[part]?.reuseReference);
      if(realEstateIsCollider(part))return `<button type="button" data-re-rig="${esc(part)}" ${!canPublish||isBusy?'disabled':''}>republish ${esc(part)} rig</button>`;
      return `<button type="button" data-re-texture="${esc(part)}">${esc(part)} texture</button>`+
        `<button type="button" data-re-image="${esc(part)}" ${!canPublish||isBusy||live[part]||shared?'disabled':''}>${shared?'reused · '+esc(part):'publish '+esc(part)+' image'}</button>`+
        `<button type="button" data-re-rig="${esc(part)}" ${!canPublish||isBusy?'disabled':''}>republish ${esc(part)} rig</button>`;
    }).join('');
    return `<tr class="${item.slug===realEstateState.selected?'active':''}" data-house="${esc(item.slug)}"><td><b>${esc(item.slug)}</b><br><small>level ${esc(item.house_level)} · variant ${esc(item.variant)}</small></td><td><small>buy ${esc(item.purchase_price)} · sell ${esc(item.sale_price)}<br>level required ${esc(item.min_level)}</small></td><td><small>${textureLines}</small></td><td class="real-estate-assets-cell">${assetLines}</td><td><div class="real-estate-row-actions"><button type="button" data-re-edit>edit</button><button type="button" data-re-fbx>replace FBX</button>${controls}<button type="button" data-re-pub-model ${!canPublish||isBusy||live.model?'disabled':''}>publish FBX</button><button type="button" data-re-publish ${!canPublish||isBusy||item.status==='PUBLISHED'?'disabled':''}>publish changed</button><button type="button" data-re-sync ${isBusy||item.status!=='PUBLISHED'?'disabled':''}>sync Studio</button><button type="button" class="real-estate-delete" data-re-delete ${isBusy?'disabled':''}>delete house</button></div></td></tr>`;
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
    tr.querySelector('[data-re-delete]').onclick=()=>realEstateDelete(row);
    for(const button of tr.querySelectorAll('[data-re-atlas-id]')){
      button.onclick=()=>realEstateChooseAtlas(row,button.dataset.reAtlasPart,Number(button.dataset.reAtlasId));
    }
    for(const button of tr.querySelectorAll('[data-re-atlas-retry]')){
      button.onclick=()=>realEstateSync(row.slug).then(()=>realEstateLoad());
    }
  }
  realEstateRenderAtlasLibrary(rows);
  const row=realEstateSelected();
  const busy=row&&realEstatePublicationBusy(row.slug);
  $('real-estate-publish').disabled=!row||!realEstateState.data?.publication?.configured||row.status==='PUBLISHED'||busy;
  $('real-estate-sync').disabled=!row||row.status!=='PUBLISHED'||busy;
  const job=realEstateState.publicationJob;
  $('real-estate-publish-status').textContent=busy
    ? `Publishing ${job.scope} · ${job.step} (continues in Host Agent if this tab closes)`
    : job?.slug===row?.slug&&job.status==='failed'
      ? `Last publication failed · ${job.step}: ${job.error}`
      : row?`${row.status} · ${(row.meshParts||[]).map(p=>p.slice(0,1).toUpperCase()+p.slice(1)+'Rig').join(' + ')} ${row.publicationCurrent?.model?'ready':'changed'} · ${row.meshParts?.map(part=>realEstateIsCollider(part)?`${part} physics only`:`${part} image ${row.publicationCurrent?.[part]?'ready':'changed'}`).join(' · ')} · Sync Studio requires all present assets ready`:'register a house first';
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
$('real-estate-atlas-house').onchange=event=>{realEstateState.atlasHouse=event.target.value;realEstateRender();};
$('real-estate-atlas-mode').onchange=event=>{realEstateState.atlasMode=event.target.value;if(!realEstateState.atlasHouse&&realEstateState.atlasMode!=='all')realEstateState.atlasHouse=realEstateState.selected||'';realEstateRender();};
for(const id of ['real-estate-type','real-estate-level','real-estate-variant'])$(id).addEventListener('input',realEstateIdentity);

if (!$('real-estate-view').hidden) realEstateLoad();
