/* Real Estate registry view. Global request(), toast(), esc(), $ provided by Character Assets. */
const realEstateState = {data:null, selected:null, inspect:null, textures:{}, textureRefs:{}, reuseEnabled:{}, reuseFilters:{}, meshOptions:{}, appearance:{}, acceptWarnings:false, atlasBusy:false, registrationTarget:null};
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
    await realEstateLoad();
    if(job.status==='succeeded'){
      const latest=realEstateRows().find(item=>item.slug===slug);
      const part=job.scope?.startsWith('model:')?job.scope.slice(6):null;
      const modelsReady=part
        ?Boolean(latest?.rigAssets?.[part]?.assetId &&
          latest.rigAssets[part].publishedSha256===latest.rigPublicationHashes?.[part])
        :Boolean(latest?.publicationCurrent?.model);
      if(!modelsReady)toast(`${slug} · Model publication finished, but current mesh revisions are not confirmed. Refresh and inspect status.`,true);
      else toast(`${slug} · Model publication verified. ${latest.status==='PUBLISHED'?'Studio Sync ready':'Other house resources still need publication.'}`);
    }
  }
}

function realEstateRows(){return (Array.isArray(realEstateState.data?.items)?realEstateState.data.items:[]).filter(item=>item&&typeof item.slug==='string');}
function realEstateSelected(){return realEstateRows().find(item=>item.slug===realEstateState.selected)||null;}
function realEstateStatus(){const row=realEstateSelected();return row?.status||'LOCAL_ONLY';}
function realEstateMeshLabel(part){return part==='repair'?'restoration (legacy: repair)':part;}
function realEstateMeshDefaults(part){
  return window.game1MeshAuthoring.defaults(part);
}
function realEstateEffectiveFidelity(part,flags){
  return window.game1MeshAuthoring.effectiveFidelity(flags);
}
function realEstateNormalizePhysics(part,raw){
  return window.game1MeshAuthoring.normalize(part,raw);
}
function realEstatePhysicsStatus(flags){return window.game1MeshAuthoring.status(flags);}
function realEstatePhysicsControls(part,flags){
  return window.game1MeshAuthoring.controls(part,flags,'real-estate');
}
function realEstateRemember(){try{localStorage.setItem(REAL_ESTATE_SELECTED,realEstateState.selected||'');}catch{}}
function realEstateForm(row){
  realEstateState.selected=row?.slug||null;
  // Keep the shared Collision Blueprint picker aligned with the house editor.
  // Selecting from the library may scroll to the panel; ordinary Edit must not.
  window.game1RealEstateCollisionSelect?.(row?.slug||'', false);
  realEstateState.registrationTarget=null;
  realEstateState.pendingLod1='';
  realEstateRemember();
  realEstateState.inspect=null;
  realEstateState.acceptWarnings=Boolean(row);
  realEstateState.reuseFilters={};
  const meshNames=(row?.meshParts||[]);
  realEstateState.meshOptions=Object.fromEntries(meshNames.map(part=>[part,{
    glass:row?.meshOptions?.[part]?.glass ?? realEstateMeshDefaults(part).glass,
    noCollide:row?.meshOptions?.[part]?.noCollide ?? realEstateMeshDefaults(part).noCollide,
    collisionFidelity:row?.meshOptions?.[part]?.collisionFidelity ?? realEstateMeshDefaults(part).collisionFidelity,
    doubleSided:row?.meshOptions?.[part]?.doubleSided ?? realEstateMeshDefaults(part).doubleSided
  }]));
  realEstateState.appearance=Object.fromEntries(meshNames.map(part=>[part,{
    appearanceMode:window.game1MeshAuthoring.displayAppearanceMode(row?.meshOptions?.[part]?.appearanceMode||'material'),
    visualMaterial:row?.meshOptions?.[part]?.visualMaterial||'Plastic',
    visualColor:row?.meshOptions?.[part]?.visualColor||'#FFFFFF',
    alphaEnabled:row?.meshOptions?.[part]?.alphaEnabled===true
  }]));
  for(const part of meshNames){
    realEstateState.meshOptions[part]=realEstateNormalizePhysics(part,realEstateState.meshOptions[part]);
  }
  // A central AtlasRegistry binding is reuse even when the legacy Estate
  // texture row has reuseReference="". The binding, not the local source path,
  // determines the active published Image Asset ID.
  const referenceForPart=part=>{
    const texture=row?.textures?.[part]||{};
    if(texture.reuseReference)return texture.reuseReference;
    // Atlas identity survives pending publication and replacement. Never turn
    // an existing binding into a local PNG upload merely because it is not current.
    return texture.atlasVariantId ? `atlas:${texture.atlasVariantId}` : '';
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
  const registrationError=$('real-estate-register-error');
  registrationError.textContent='';
  registrationError.hidden=true;
  realEstateRenderRigs(row?.skeleton||null, row?.rigWarnings||[]);
  realEstateRenderTextures(row);
  realEstateRuntimeRender(row);
  realEstateRender();
}
// Real Estate owns house and per-MeshPart FULL authoring. All LOD1 geometry
// authoring now lives in the shared LOD Manager readiness surface.
function realEstateRuntimeRender(row){
  const target=$('real-estate-runtime-content');
  if(!row){target.innerHTML='<small class="muted">Register a house first.</small>';return;}
  const profile=row.runtimeProfile||{mode:'off'};
  const count=(row.meshParts||[]).filter(part=>row.partLod1?.[part]?.status==='PUBLISHED').length;
  const warnings=row.runtimeReadiness?.warnings||[];
  target.innerHTML=`<div class="real-estate-runtime-info">
    <small>${esc(row.slug)} · ${count}/${(row.meshParts||[]).length} parts published · ${esc(profile.mode)}</small>
    <p class="hint">Streaming mode and all per-MeshPart FULL / LOD1 / Unloaded distances: LOD Manager → 02 · LOD readiness → Real Estate.</p>
    <div class="status-box">${warnings.length?warnings.map(esc).join(' · '):'Studio Runtime validation pending'}</div>
  </div>`;
}

// Inspect reports the *authored* shared FBX armature for each mesh, while
// M182 publishes unweighted accessories of house_armature as static MeshParts.
// This projection is presentation-only; Python owns the publication contract.
function realEstateSharedStatic(part){
  return part?.name!=='house' && String(part?.armature||'').toLowerCase()==='house_armature'
    && !realEstatePublishedBones(part).length;
}
function realEstatePublishedBones(part){
  if(Array.isArray(part?.publicationBones))return part.publicationBones;
  // Older cached responses predate server-side ownership projection.
  const bones=Array.isArray(part?.bones)?part.bones:[];
  const legacyStatic=part?.name!=='house' && String(part?.armature||'').toLowerCase()==='house_armature'
    && !(part?.influencedBones||[]).length;
  return legacyStatic?[]:bones;
}
// Render roles from authored bone names, never guess rig ownership from a name.
function realEstateBoneRole(part, name){
  if(part==='door' && name==='door_01_hinge_socket')return 'hinge';
  if(name.endsWith('_socket'))return 'socket';
  return 'bone';
}
function realEstateRigMode(part){
  const names=new Set(realEstatePublishedBones(part).map(b=>b.name));
  if(realEstateSharedStatic(part))return 'Статичный MeshPart · общий исходный скелет, без копии костей';
  if(part.name==='door')return names.has('door_01_hinge_socket')
    ? 'Шарнир двери · отдельный Model Asset' : 'Дверь без hinge pivot';
  if(part.name==='house')return `${[...names].filter(n=>n.endsWith('_socket')).length} авторских сокетов · сохраняются в Model Asset дома`;
  return names.size?'Собственные / взвешенные кости · отдельный Model Asset':'Статичный MeshPart · без костей';
}
function realEstateRenderRigs(analysis, warnings=[]){
  const meshes=analysis?.meshes||[];
  const summary=$('real-estate-rig');
  summary.textContent=meshes.length
    ? meshes.map(part=>`${realEstateMeshLabel(part.name)}: ${realEstatePublishedBones(part).length} костей при публикации`).join(' · ')+' · подробнее'
    : 'choose an FBX to view mesh / bone details';
  $('real-estate-bone-list').innerHTML=meshes.map(part=>{
    const bones=realEstatePublishedBones(part);
    const mode=realEstateRigMode(part);
    const source=part.bones||[];
    const shared=realEstateSharedStatic(part);
    return `<section class="real-estate-bone-group"><strong>${esc(realEstateMeshLabel(part.name))} · ${esc(part.armature||'без Armature')}</strong>
      <small class="real-estate-rig-mode">${esc(mode)}</small>
      ${bones.length?window.game1MeshAuthoring.boneList(bones,[],name=>realEstateBoneRole(part.name,name)):shared
        ? `<small class="muted">В исходном FBX: ${source.length} общих костей ${esc(part.armature)}. В Model Asset этой статичной части они не экспортируются.</small>`
        : '<small class="muted">Нет костей для публикации</small>'}</section>`;
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
// Display names derive from the actual atlas, never from its first model owner.
// Atlas selection is independent from model registration slugs.
function realEstateReuseLabel(entry){
  return window.game1AtlasIdentity.label({filename:entry.filename||entry.path,
    atlasKey:entry.group==='atlas'?entry.label:''},{assetId:entry.assetId});
}
function realEstatePublishedAtlasChoices(){
  const choices=new Map();
  for(const entry of realEstateState.data?.textureReferences||[]){
    if((entry.group==='atlas'||String(entry.reference||'').startsWith('atlas:'))&&entry.assetId){
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
  return [...choices.values()];
}
function realEstateReuseOptions(part){
  const active=realEstateState.textureRefs[part]||'';
  const query=String(realEstateState.reuseFilters[part]?.query||'').trim().toLocaleLowerCase();
  const all=[...realEstatePublishedAtlasChoices()];
  // The published-only picker must still show the currently bound variant,
  // including unpublished or pending-republication atlases. This is not a
  // way to bind arbitrary unpublished variants to other houses.
  const current=realEstateSelected()?.textures?.[part];
  if(active.startsWith('atlas:') && String(current?.atlasVariantId||'')===active.slice(6)
      && !all.some(entry=>entry.reference===active)){
    all.push({reference:active,group:'atlas',label:current.atlasKey||'',
      filename:current.filename||current.path||'',path:current.path||'',
      assetId:current.assetId||'',existingUnpublished:true});
  }
  if(part!=='house'){
    const owner=realEstateSelected()?.textures?.house||{};
    const path=realEstateState.textures.house||owner.path||'';
    if(path||owner.filename)all.push({reference:'same:house',group:'local',
      filename:owner.filename||String(path).split(/[\\/]/).pop(),assetId:owner.assetId||'',
      atlasKey:owner.atlasKey||''});
  }
  const choiceByRef=new Map(all.filter(e=>e?.reference).map(e=>[e.reference,e]));
  const candidates=[...choiceByRef.values()].filter(e=>{
    const identity=window.game1AtlasIdentity.describe({filename:e.filename||e.path,
      atlasKey:e.group==='atlas'?e.label:(e.atlasKey||'')});
    return e.reference===active||!query||[identity.key,identity.name,identity.variant,
      identity.resolution,identity.filename,e.assetId].some(v=>String(v||'').toLocaleLowerCase().includes(query));
  });
  // One published resolution is one atlas identity regardless of its consumers.
  candidates.sort((a,b)=>{
    const ai=window.game1AtlasIdentity.describe({filename:a.filename||a.path,atlasKey:a.group==='atlas'?a.label:a.atlasKey});
    const bi=window.game1AtlasIdentity.describe({filename:b.filename||b.path,atlasKey:b.group==='atlas'?b.label:b.atlasKey});
    return ai.key.localeCompare(bi.key)||
      ((a.assetId&&a.assetId===b.assetId)?Number(b.reference===active)-Number(a.reference===active):0)||
      (window.game1AtlasIdentity.pixelArea(bi.resolution)-window.game1AtlasIdentity.pixelArea(ai.resolution))||
      String(a.reference).localeCompare(String(b.reference));
  });
  const visible=[];
  const ids=new Set();
  for(const e of candidates){
    const id=String(e.assetId||'');
    if(id&&ids.has(id)&&e.reference!==active)continue;
    if(id)ids.add(id);
    visible.push(e);
  }
  const result=['<option value="">choose reuse atlas…</option>'];
  let previous='';
  for(const e of visible){
    const identity=window.game1AtlasIdentity.describe({filename:e.filename||e.path,
      atlasKey:e.group==='atlas'?e.label:(e.atlasKey||'')});
    if(identity.key!==previous){
      if(previous)result.push('</optgroup>');
      result.push(`<optgroup label="${esc(identity.key)}">`);
      previous=identity.key;
    }
    result.push(`<option value="${esc(e.reference)}">${esc(realEstateReuseLabel(e))}${e.existingUnpublished?' · bound, awaiting publication':''}</option>`);
  }
  if(previous)result.push('</optgroup>');
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
function realEstateRenderTextures(row){
  const host=$('real-estate-mesh-textures');
  // Rebuilds (mode changes / texture browsing) keep expanded editors open.
  // Switching to another house through realEstateForm(row) starts collapsed.
  const openParts=new Set(row ? [] : Array.from(host.querySelectorAll?.('.real-estate-texture-row[open]')||[], element=>element.dataset.texturePart));
  const parts=realEstateParts();
  for(const part of parts){
    realEstateState.meshOptions[part]=realEstateNormalizePhysics(part,realEstateState.meshOptions[part]);
    realEstateState.appearance[part] ||= {appearanceMode:'material',visualMaterial:'Plastic',visualColor:'#FFFFFF',alphaEnabled:false};
  }
  const options=realEstateOptions();
  host.innerHTML='<small class="real-estate-physics-caution">Static house collision will use a separately authored Roblox Parts blueprint. Visual meshes default to No Collide.</small>'+parts.map(part=>{
    let selected=realEstateState.textures[part]||'';
    const reuse=realEstateState.reuseEnabled[part]===true;
    if(realEstateState.appearance[part].appearanceMode!=='material' && !selected && !reuse){
      const guess=options.find(item=>item.name.toLowerCase().startsWith(part+'.')||item.name.toLowerCase().startsWith(part+'_'));
      if(guess)selected=guess.path;
    }
    realEstateState.textures[part]=selected;
    const choices=[`<option value="">choose texture…</option>`];
    if(selected && !options.some(item=>item.path===selected)){
      choices.push(`<option value="${esc(selected)}">${esc(selected.split(/[\\/]/).pop())} · selected</option>`);
    }
    for(const item of options)choices.push(`<option value="${esc(item.path)}">${esc(item.name)}</option>`);
    const filters=realEstateState.reuseFilters[part]||{query:''};
    realEstateState.reuseFilters[part]=filters;
    const flags=realEstateState.meshOptions[part];
    const appearance=realEstateState.appearance[part];
    const atlas=appearance.appearanceMode!=='material';
    const material=true;
    const materials=realEstateState.data?.visualMaterials||[];
    return `<details class="real-estate-texture-row" data-texture-part="${esc(part)}" ${openParts.has(part)?'open':''}>
      <summary class="real-estate-texture-heading"><strong class="real-estate-mesh-name">${esc(realEstateMeshLabel(part))}</strong><span class="real-estate-mesh-kind">Visual mesh</span></summary>
      <div class="real-estate-texture-body">
      <div class="real-estate-mesh-switches" role="group" aria-label="${esc(part)} mesh appearance">
        <label>Appearance <select id="real-estate-appearance-${esc(part)}"><option value="material" ${appearance.appearanceMode==='material'?'selected':''}>Material + Color</option><option value="material_atlas" ${appearance.appearanceMode==='material_atlas'?'selected':''}>Material + Color + Atlas</option></select></label>
        <span id="real-estate-material-controls-${esc(part)}" ${!material?'hidden':''}><select id="real-estate-material-${esc(part)}" aria-label="${esc(part)} Roblox material">${materials.map(item=>`<option value="${esc(item.id)}" ${appearance.visualMaterial===item.id?'selected':''} ${item.requiresTexture&&appearance.appearanceMode==='material'?'disabled':''}>${esc(item.label)}${item.requiresTexture?' · requires texture':''}</option>`).join('')}</select>
        <input type="color" id="real-estate-color-${esc(part)}" aria-label="${esc(part)} color" value="${esc(appearance.visualColor)}"></span>
        <label id="real-estate-alpha-controls-${esc(part)}" ${!atlas?'hidden':''}><input type="checkbox" id="real-estate-alpha-${esc(part)}" ${appearance.alphaEnabled?'checked':''}> Alpha transparency</label>
        <label class="real-estate-glass-toggle" title="Studio MeshPart Transparency = 0.02 (if checked)"><input type="checkbox" id="real-estate-glass-${esc(part)}" ${flags.glass?'checked':''}> Glass · 0.02</label>
        <label class="real-estate-physics-toggle" title="Disable physics collisions, touch events, and spatial queries for this mesh"><input type="checkbox" id="real-estate-nocollide-${esc(part)}" ${flags.noCollide?'checked':''}> No Collide</label>
        <label class="real-estate-reuse-toggle" title="Bind this mesh to an existing published Atlas Registry variant. Reuse never uploads another Roblox Image Asset."><input type="checkbox" id="real-estate-reuse-${esc(part)}" ${reuse?'checked':''}> Reuse atlas</label>
      </div>
      ${appearance.appearanceMode==='material_atlas'?'<small class="muted">Atlas takes precedence over the Roblox material texture on a single MeshPart. Material and Color remain assigned; for separately visible surfaces use separate meshes.</small>':''}
      ${realEstatePhysicsControls(part,flags)}
      <div id="real-estate-owned-${esc(part)}" class="real-estate-texture-owned" ${!atlas||reuse?'hidden':''}>
        <select aria-label="${esc(part)} texture" id="real-estate-texture-${esc(part)}">${choices.join('')}</select>
        <button type="button" id="real-estate-browse-${esc(part)}">browse…</button>
        <small class="muted real-estate-texture-path" id="real-estate-texture-path-${esc(part)}" title="${esc(selected)}">${esc(selected||'no texture selected')}</small>
      </div>
      <div id="real-estate-shared-${esc(part)}" class="real-estate-texture-shared" ${atlas&&reuse?'':'hidden'}>
        <div class="real-estate-reuse-filters">
          <input type="search" id="real-estate-reuse-search-${esc(part)}" aria-label="Search ${esc(part)} reuse" placeholder="search atlas name, variant, resolution or ID…" value="${esc(filters.query)}">
        </div>
        <select aria-label="${esc(part)} reused texture" id="real-estate-reference-${esc(part)}"></select>
        <small class="hint">Atlases are identified by filename and Image Asset ID, independent of the first model that used them (no upload). For changed pixels, use Republish instead.</small>
      </div></div></details>`;
  }).join('');
  for(const part of parts){
    $(`real-estate-appearance-${part}`).onchange=event=>{
      realEstateState.appearance[part].appearanceMode=event.target.value;
      if(event.target.value==='material')realEstateState.appearance[part].alphaEnabled=false;
      realEstateRenderTextures();
    };
    $(`real-estate-material-${part}`).onchange=event=>{
      realEstateState.appearance[part].visualMaterial=event.target.value;
    };
    $(`real-estate-color-${part}`).oninput=event=>{
      realEstateState.appearance[part].visualColor=event.target.value;
    };
    $(`real-estate-alpha-${part}`).onchange=event=>{
      realEstateState.appearance[part].alphaEnabled=event.target.checked;
    };
    $(`real-estate-nocollide-${part}`).onchange=event=>{
      const flags=realEstateState.meshOptions[part];
      flags.noCollide=event.target.checked;
      flags.collisionFidelity=realEstateEffectiveFidelity(part,flags);
      const select=$(`real-estate-fidelity-${part}`);
      select.value=flags.collisionFidelity;
      select.disabled=flags.noCollide;
      $(`real-estate-physics-state-${part}`).textContent=realEstatePhysicsStatus(flags);
    };
    $(`real-estate-fidelity-${part}`).onchange=event=>{
      const flags=realEstateState.meshOptions[part];
      flags.collisionFidelity=event.target.value;
      event.target.value=flags.collisionFidelity;
    };
    $(`real-estate-doublesided-${part}`).onchange=event=>{
      realEstateState.meshOptions[part].doubleSided=event.target.checked;
    };
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
    const search=$(`real-estate-reuse-search-${part}`);
    search.oninput=()=>{filters.query=search.value;realEstateUpdateReuseOptions(part);};
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
function realEstateRegisterPlotType(slug){
  // A deleted model is not a deleted house TYPE: preserve its plot pivots.
  const match=/^([a-z][a-z0-9_]*)_level([1-9][0-9]*)_([0-9]{2,})$/.exec(slug);
  if(!match)return;
  realEstateForm(null); // Never turn the deleted registration into an edit.
  realEstateState.registrationTarget=slug;
  $('real-estate-type').value=match[1];
  $('real-estate-level').value=match[2];
  $('real-estate-variant').value=match[3];
  realEstateIdentity();
  $('real-estate-fbx').textContent=`Choose a NEW FBX for ${slug} · saved Plot pivots remain`;
  $('real-estate-choose').focus();
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
    if(!realEstateState.selected && !realEstateState.registrationTarget){
      $('real-estate-type').value=inspection.houseType;
      $('real-estate-level').value=inspection.level;
      $('real-estate-variant').value=inspection.variant;
    }
    realEstateRenderRigs(inspection.analysis, warnings);
    // Existing mesh textures remain selected while FBX is replaced independently.
    if(!realEstateState.selected){
      realEstateState.textures={};realEstateState.textureRefs={};realEstateState.reuseEnabled={};realEstateState.meshOptions={};realEstateState.appearance={};
      // New visual meshes default to native Roblox Material + Color. Atlas is
      // an explicitly selected mode, not a registration requirement.
    }
    realEstateRenderTextures();
    realEstateIdentity();
    toast('FBX analyzed · Material + Color by default');
    return true;
  } catch(error) {toast(error.message,true);return false;}
}
function realEstatePayload(){
  const parts=realEstateParts();
  for(const part of parts){
    if(realEstateState.appearance[part]?.appearanceMode!=='material'
      && realEstateState.reuseEnabled[part] && !realEstateState.textureRefs[part]){
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
    meshOptions:Object.fromEntries(parts.map(part=>{
      const flags=realEstateNormalizePhysics(part,realEstateState.meshOptions[part]);
      return [part,{
        glass:Boolean(flags.glass),
        noCollide:flags.noCollide===true,
        collisionFidelity:flags.collisionFidelity,
        doubleSided:flags.doubleSided,
        ...realEstateState.appearance[part]
      }];
    })),
    acceptWarnings:realEstateState.acceptWarnings};
}
async function realEstateRegister(){
  const errorBox=$('real-estate-register-error');
  errorBox.hidden=true;errorBox.textContent='';
  try{
    $('real-estate-register').disabled=true;
    const row=await request('/api/real-estate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(realEstatePayload())});
    realEstateState.selected=row.slug;
    await realEstateLoad();
    if(row.studioSyncStatus==='pending_studio_sync')toast(`Mesh settings saved · Studio Sync pending: ${row.studioError||'Studio unavailable'}`,true);
    else toast(`Real Estate registered · ${row.slug}${row.studioSyncStatus==='synced'?' · Studio updated':''}`);
    return true;
  }catch(error){
    // API returns the server-side validation reason (not just HTTP 400).
    // Keep it beside Register / Save; a toast alone is easy to miss.
    errorBox.textContent=`Register / Save: ${error.message}`;
    errorBox.hidden=false;
    toast(error.message,true);
    return false;
  }finally{$('real-estate-register').disabled=false;}
}
async function realEstateSync(slug, part=null, {throwOnError=false}={}){
  const row=realEstateRows().find(item=>item.slug===slug);
  if(!row)return null;
  try{
    toast(`Syncing ${slug}${part?' / '+part:''} · template and managed placed houses…`,false,true);
    const result=await window.game1StudioSync.run('real-estate',slug,{part});
    // The server already validates the Studio protocol before reporting success.
    // Do not duplicate its version gate here: v2/v3 drift caused a false error
    // after a successful M379 Sync.
    const stats=result.studio?.realEstateStats;
    if(!stats || typeof stats!=='object'){
      throw new Error('Studio Sync response is missing Real Estate statistics. Check Studio Bridge logs.');
    }
    const warnings=stats.rigWarnings||[];
    const missing=stats.missingSockets||[];
    const found=Number(stats.workspaceModelsFound||0);
    const updated=Number(stats.workspaceModelsUpdated||0);
    const physics=Number(stats.workspaceCollisionRigsUpdated||0);
    const incomplete=found===0||missing.length>0||warnings.length>0||updated<found;
    const summary=(found===0
      ? `Studio template updated · NO matching placed houses found (0/0)`
      : `Studio template updated · placed houses ${updated}/${found}`)+
      (physics?` · collision rigs ${physics}`:'')+
      (missing.length?` · sockets missing ${missing.length}`:'')+
      (warnings.length?` · ${warnings.length} warning(s)`:'');
    toast(summary,incomplete);
    if(warnings.length||missing.length){
      const box=$('real-estate-rig-warnings');
      box.hidden=false;
      box.innerHTML=`<strong>Studio Sync diagnostics</strong><ul>${[...warnings,...missing.map(name=>'Missing socket: '+name)].map(w=>`<li>${esc(w)}</li>`).join('')}</ul><small>Workspace models with the matching Game1RealEstateSlug are updated regardless of folder or a copied template flag. Missing instances need a managed slug.</small>`;
    }
    await realEstateLoad();
    return result;
  }catch(error){if(throwOnError)throw error;toast(`Studio Sync: ${error.message}`,true);return null;}
}
async function realEstatePublish(scope='all'){
  const row=realEstateSelected(); if(!row)return null;
  const button=$('real-estate-publish');
  try{
    button.disabled=true;
    toast(`Publishing ${scope==='all'?'changed Real Estate assets':scope} for ${row.slug}…`,false,true);
    const result=await request('/api/real-estate/'+encodeURIComponent(row.slug)+'/publish-async',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({description:$('real-estate-description').value,scope})});
    if(!result?.job || result.job.scope!==scope){
      throw Error('A different Real Estate publication is running; selected mesh was not published');
    }
    realEstateState.publicationJob=result.job;
    realEstateRender();
    await realEstateWatchPublication(row.slug,true);
    return result;
  }catch(error){toast(error.message,true);return null;}finally{
    button.disabled=!realEstateSelected()||!realEstateState.data?.publication?.configured||realEstateStatus()==='PUBLISHED'||realEstatePublicationBusy(realEstateState.selected);
  }
}
// Publish only the named mesh from a standalone FBX or a whole-house FBX.
// No changes to other mesh sources, textures, asset IDs or Studio transforms.
async function realEstateReplaceMesh(row, part){
  try{
    if(realEstatePublicationBusy(row.slug))throw Error('A publication is already running for this house');
    const chosen=await request('/api/files/choose-real-estate-model',{method:'POST'});
    if(!chosen.path)return;
    const endpoint='/api/real-estate/'+encodeURIComponent(row.slug);
    const preview=await request(endpoint+'/mesh-inspect',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({part,sourcePath:chosen.path})});
    const boneCount=preview.mesh?.bones?.length||0;
    const same=preview.sourceSha256===preview.currentSha256;
    if(!window.confirm(`Replace only ${row.slug} / ${part} from:
${preview.sourcePath}

`+
      `Vertices: ${preview.mesh.vertices} · Bones: ${boneCount}
`+
      `${same?'Identical source bytes.':'A new Model Asset ID will be required after publication.'}

`+
      `Other meshes, images and their Roblox IDs will NOT change. Continue?`))return;
    const saved=await request(endpoint+'/mesh-source',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({part,sourcePath:preview.sourcePath,expectedRevision:row.revision})});
    // A file picker success is not a registered revision. Verify the server persisted
    // precisely the selected part and SHA before offering publication/Studio Sync.
    if(saved?.meshSources?.[part]?.sha256!==preview.sourceSha256 ||
       saved?.rigSourceHashes?.[part]!==preview.sourceSha256){
      throw Error(part+': chosen FBX was not committed as this mesh revision');
    }
    await realEstateLoad();
    toast(`${part} · FBX revision saved. Next: Publish model.`);
    return true;
  }catch(error){toast(error.message,true);return false;}
}
async function realEstateReplaceFbx(row){
  realEstateForm(row);
  if(await realEstateChooseFbx())await realEstateRegister();
}
// Central Atlas Registry presentation; one independent binding per Estate mesh.
// Colors are relative ranks, never absolute resolution thresholds.
const REAL_ESTATE_ATLAS_COLORS = ['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'];
function realEstateAtlasVersionSelector(texture, part){
  const choices=texture?.atlasVersionChoices||[];
  if(!choices.length||new Set(choices.map(v=>v.version)).size<2){
    return texture?.atlasVersion?`<span class="real-estate-atlas-version-tag" title="Atlas version">v${esc(texture.atlasVersion)}</span>`:'';
  }
  // A version can contain several resolutions; selecting an option changes
  // only this mesh binding. Unpublished alternatives cannot be selected.
  const currentId=Number(texture.atlasVariantId||0);
  const options=choices.map(v=>{
    const selected=Number(v.id)===currentId;
    const enabled=Boolean(v.current&&v.published_id);
    return `<option value="${Number(v.id)}" ${selected?'selected':''} ${!enabled?'disabled':''}>v${esc(v.version)} · ${esc(v.resolution)}${enabled?'':' · unpublished'}</option>`;
  }).join('');
  const placeholder=currentId?'':`<option value="" selected>Choose published version…</option>`;
  return `<label class="real-estate-atlas-version-picker">Version / resolution <select data-re-atlas-version-part="${esc(part)}" aria-label="${esc(part)} atlas version" ${realEstateState.atlasBusy?'disabled':''}>${placeholder}${options}</select></label>`;
}
function realEstateAtlasDots(texture, part){
  const variants=[...(texture?.atlasVariants||[])].sort((a,b)=>(Number(b.width)*Number(b.height)-Number(a.width)*Number(a.height))||Number(b.width)-Number(a.width)||Number(b.height)-Number(a.height));
  if(!variants.length)return '';
  const dots=variants.map((variant,index)=>{
    const active=Number(texture.atlasVariantId)===Number(variant.id) ||
      (!texture.atlasVariantId && Boolean(texture.assetId) &&
       String(texture.assetId)===String(variant.published_id||''));
    const name=variant.filename||`${variant.atlas_key}_${variant.resolution}_atlas.png`;
    const hint=`${active?'CURRENT · ':''}${variant.resolution} · ${name}${variant.current?'':' · publish first'}`;
    return `<button type="button" class="deco-atlas-dot ${active?'is-active':''}" style="--dot-color:${REAL_ESTATE_ATLAS_COLORS[Math.min(index,4)]}" data-re-atlas-part="${esc(part)}" data-re-atlas-id="${Number(variant.id)}" title="${esc(hint)}" aria-label="${esc(hint)}" aria-pressed="${active}" ${(!variant.current||realEstateState.atlasBusy)?'disabled':''} data-re-atlas-active="${active?'true':'false'}"><span></span></button>`;
  });
  return `<div class="deco-atlas-dots real-estate-atlas-dots" aria-label="Registered atlas resolutions">${dots.slice(0,5).join('')}${dots.length>5?`<details class="deco-atlas-more"><summary>+${dots.length-5}</summary><div>${dots.slice(5).join('')}</div></details>`:''}</div>`;
}
async function realEstateChooseAtlas(row,part,variantId,mode='variant'){
  const texture=row.textures?.[part];
  if(!texture||realEstateState.atlasBusy||Number(texture.atlasVariantId)===Number(variantId))return;
  realEstateState.atlasBusy=true;
  realEstateRender();
  try{
    const result=await request(`/api/real-estate/${encodeURIComponent(row.slug)}/atlas-binding`,{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({part,variantId,mode,expectedRevision:texture.reuseReference?0:Number(texture.atlasBindingRevision||0)})
    });
    await realEstateLoad();
    if(result.studioSyncStatus==='pending_studio_sync'){
      toast(`Atlas selected · Studio sync pending: ${result.studioError||'Studio unavailable'}`,true);
    }else toast(`${row.slug} / ${part} · atlas changed and Studio synced`);
    return result;
  }catch(error){toast(`Atlas change: ${error.message}`,true);await realEstateLoad();return null;}
  finally{realEstateState.atlasBusy=false;realEstateRender();}
}
async function realEstateDelete(row){
  if(realEstatePublicationBusy(row.slug)){toast('Wait for the publication to finish before deleting',true);return;}
  await window.game1AssetRetirement.open({kind:'estate',slug:row.slug,onDone:async(result)=>{
    if(realEstateState.selected===row.slug){realEstateState.selected=null;realEstateRemember();}
    await realEstateLoad();
    if(typeof decoAssetLoad==='function')await decoAssetLoad();
    toast(`Retired ${result.deleted.length} registration(s) · Studio templates unchanged`);
  }});
}
function realEstateRender(){
  const rows=realEstateRows();
  $('real-estate-count').textContent=rows.length;
  $('real-estate-library-count').textContent=rows.length;
  const orphaned=(realEstateState.data?.unregisteredPlotTypes||[]).filter(item=>
    item && typeof item.slug==='string' && Number.isInteger(item.plotCount));
  const registeredButtons=rows.map(item=>`<button type="button" data-real-estate="${esc(item.slug)}" class="${item.slug===realEstateState.selected?'active':''}">${esc(item.slug)} · ${esc(item.status)}</button>`).join('');
  const restoreButtons=orphaned.map(item=>`<button type="button" data-re-register="${esc(item.slug)}" title="Register a new model while retaining ${item.plotCount} Plot pivots">${esc(item.slug)} · ${item.plotCount} plots · Register again</button>`).join('');
  $('real-estate-tree').innerHTML=registeredButtons+restoreButtons || '<span class="muted">No houses registered.</span>';
  for(const node of $('real-estate-tree').querySelectorAll('[data-real-estate]'))node.onclick=()=>realEstateForm(rows.find(row=>row.slug===node.dataset.realEstate));
  for(const node of $('real-estate-tree').querySelectorAll('[data-re-register]'))node.onclick=()=>realEstateRegisterPlotType(node.dataset.reRegister);
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
      const isMaterial=item.meshOptions?.[part]?.appearanceMode==='material';
      const filename=isMaterial?`${item.meshOptions[part].visualMaterial} ${item.meshOptions[part].visualColor}`:(tex.filename||tex.path?.split('/').pop()||tex.reuseReference||'—')+(item.meshOptions?.[part]?.appearanceMode==='material_atlas'?` · ${item.meshOptions[part].visualMaterial} ${item.meshOptions[part].visualColor}`:'');
      return `<div class="real-estate-texture-line"><strong>${esc(realEstateMeshLabel(part))}</strong>: <span class="real-estate-texture-filename">${esc(filename)}</span>${!isMaterial&&tex.atlasLegacyWarning?'<span class="deco-atlas-warning" title="Expected &lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png"> ⚠️</span>':''}${isMaterial?'':realEstateAtlasDots(tex,part)+realEstateAtlasVersionSelector(tex,part)}<button type="button" class="real-estate-texture-manage" data-re-texture="${esc(part)}">Manage atlas</button>${tex.atlasSyncStatus==='pending_studio_sync'?'<button type="button" data-re-atlas-retry="'+esc(part)+'" class="deco-atlas-retry">Sync pending · retry</button>':''}</div>`;
    }).join('');
    const carrierLine=`<div class="real-estate-carrier-line"><div class="real-estate-mesh-card-header"><strong>Rig carrier · sockets</strong></div><div class="real-estate-asset-identities"><span class="real-estate-asset-id real-estate-asset-model"><span>model</span><code>${asset(rigs.rig_carrier?.assetId,Boolean(rigs.rig_carrier?.assetId&&item.publicationCurrent?.model))}</code></span></div><small class="real-estate-mesh-source-label">Independent technical Model Asset</small></div>`;
    const assetLines=carrierLine+parts.map(part=>`<div class="real-estate-asset-part">
      <div class="real-estate-mesh-card-header"><strong class="real-estate-asset-part-name">${esc(realEstateMeshLabel(part))}</strong>
        <button type="button" class="real-estate-manage" data-re-manage="${esc(part)}">Manage mesh</button></div>
      <div class="real-estate-asset-identities">
        <span class="real-estate-asset-id real-estate-asset-model"><span>model</span><code>${asset(rigs[part]?.assetId,rigs[part]?.publishedSha256===item.rigPublicationHashes?.[part])}</code></span>
        <span class="real-estate-asset-id real-estate-asset-image"><span>image</span><code>${item.meshOptions?.[part]?.appearanceMode==='material'?'not required':asset(textures[part]?.assetId,live[part])}</code></span>
      </div>
      <small class="real-estate-mesh-source-label">${item.meshSources?.[part]?'Independent FBX revision':'Original house FBX'}</small>
      </div>`).join('');
    return `<tr class="${item.slug===realEstateState.selected?'active':''}" data-house="${esc(item.slug)}"><td class="real-estate-house-cell"><b>${esc(item.slug)}</b><small>level ${esc(item.house_level)} · variant ${esc(item.variant)}</small><small class="real-estate-house-economy">buy ${esc(item.purchase_price)} · sell ${esc(item.sale_price)}</small><small class="real-estate-house-economy">level required ${esc(item.min_level)}</small></td><td><small>${textureLines}</small></td><td class="real-estate-assets-cell">${assetLines}</td><td><div class="real-estate-row-actions"><button type="button" data-re-edit>Edit house</button><button type="button" data-re-fbx title="Replace whole-house FBX; changed parts require new Model Asset IDs">Replace full FBX</button><button type="button" data-re-publish ${!canPublish||isBusy||item.status==='PUBLISHED'?'disabled':''}>Publish all changes</button><button type="button" data-re-sync ${isBusy||item.status!=='PUBLISHED'?'disabled':''} title="${esc(item.status==='PUBLISHED'?'Sync all published house parts':'Publish every changed house Model and required atlas before full Sync')}">Sync entire house</button><button type="button" data-re-collision>Collision Blueprint</button><button type="button" class="real-estate-delete" data-re-delete ${isBusy?'disabled':''}>Delete house</button></div></td></tr>`;
  }).join('')||'<tr><td colspan="4" class="muted">No registered houses yet.</td></tr>';
  for(const tr of tbody.querySelectorAll('[data-house]')){
    const row=rows.find(item=>item.slug===tr.dataset.house);
    tr.querySelector('[data-re-edit]').onclick=()=>realEstateForm(row);
    tr.querySelector('[data-re-fbx]').onclick=()=>realEstateReplaceFbx(row);
    for(const button of tr.querySelectorAll('[data-re-manage]')){
      button.onclick=()=>realEstateMeshWorkflowOpen(row.slug,button.dataset.reManage);
    }
    for(const button of tr.querySelectorAll('[data-re-texture]')){
      button.onclick=()=>realEstateMeshWorkflowOpen(row.slug,button.dataset.reTexture,'texture');
    }
    tr.querySelector('[data-re-publish]').onclick=async()=>{realEstateForm(row);await realEstatePublish('all');};
    tr.querySelector('[data-re-sync]').onclick=()=>realEstateSync(row.slug);
    tr.querySelector('[data-re-collision]').onclick=()=>window.game1RealEstateCollisionSelect?.(row.slug);
    tr.querySelector('[data-re-delete]').onclick=()=>realEstateDelete(row);
    for(const button of tr.querySelectorAll('[data-re-atlas-id]')){
      button.onclick=()=>realEstateChooseAtlas(row,button.dataset.reAtlasPart,Number(button.dataset.reAtlasId));
    }
    for(const selector of tr.querySelectorAll('[data-re-atlas-version-part]')){
      selector.onchange=()=>{
        const id=Number(selector.value);
        if(id)realEstateChooseAtlas(row,selector.dataset.reAtlasVersionPart,id);
      };
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
    : row && job && job.slug===row.slug && job.status==='failed'
      ? `Last publication failed · ${job.step}: ${job.error}`
      : row?`${row.status} · ${(row.meshParts||[]).map(p=>p.slice(0,1).toUpperCase()+p.slice(1)+'Rig').join(' + ')} ${row.publicationCurrent?.model?'ready':'changed'} · ${row.meshParts?.map(part=>`${part} image ${row.publicationCurrent?.[part]?'ready':'changed'}`).join(' · ')} · Sync Studio requires all present assets ready`:'register a house first';
  realEstateIdentity();
  if(typeof game1RealEstatePlacementRender==='function')game1RealEstatePlacementRender();
  if(typeof realEstateMeshWorkflowRender==='function')realEstateMeshWorkflowRender();
}
async function realEstateLoad(){
  try{
    const snapshot=await request('/api/real-estate');
    if(!snapshot||!Array.isArray(snapshot.items)){throw Error('Real Estate API returned no registered-houses list. Reload Control Center.');}
    realEstateState.data=snapshot;
    if(typeof game1RealEstateCollisionRefresh==='function')game1RealEstateCollisionRefresh(snapshot.items);
    if(!realEstateState.selected){try{realEstateState.selected=localStorage.getItem(REAL_ESTATE_SELECTED)||null;}catch{}}
    if(realEstateState.selected && !realEstateSelected())realEstateState.selected=null;
    realEstateForm(realEstateSelected());
    if(typeof game1RealEstatePlacementLoad==='function')await game1RealEstatePlacementLoad();
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
