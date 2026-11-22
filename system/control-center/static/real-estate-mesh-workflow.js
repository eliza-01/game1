/* M234 · Real Estate mesh editor. Uses the SAME consumer atlas editor as
 * Location Assets; Real Estate retains house-specific Model publication/Sync.
 */
const realEstateMeshWorkflow={slug:'',part:'',tab:'model',busy:false,result:'',error:false,lodSource:'',
  atlas:window.game1ConsumerAtlasEditor.newState()};
function realEstateMeshWorkflowEnsure(){
  return window.game1AssetWorkflowDialog.ensure('real-estate-mesh-dialog','Manage Real Estate mesh',()=>{
    realEstateMeshWorkflow.slug='';realEstateMeshWorkflow.part='';
  });
}
function realEstateMeshWorkflowCurrent(){
  const row=realEstateRows().find(item=>item.slug===realEstateMeshWorkflow.slug);
  return {row,part:realEstateMeshWorkflow.part};
}
function realEstateMeshWorkflowOpen(slug,part,tab='model'){
  const row=realEstateRows().find(item=>item.slug===slug);
  if(!row||!(row.meshParts||[]).includes(part))return;
  realEstateMeshWorkflow.slug=slug;realEstateMeshWorkflow.part=part;
  realEstateMeshWorkflow.tab=tab;realEstateMeshWorkflow.lodSource='';
  realEstateMeshWorkflow.result='';realEstateMeshWorkflow.error=false;
  realEstateMeshWorkflow.atlas=window.game1ConsumerAtlasEditor.newState();
  realEstateForm(row);
  const d=realEstateMeshWorkflowEnsure();realEstateMeshWorkflowRender();
  if(!d.open)d.showModal();
}
function realEstateMeshWorkflowMessage(value,error=false){
  realEstateMeshWorkflow.result=String(value||'');realEstateMeshWorkflow.error=Boolean(error);
}
async function realEstateMeshWorkflowRun(label,action){
  if(realEstateMeshWorkflow.busy)return;
  realEstateMeshWorkflow.busy=true;realEstateMeshWorkflowMessage(label+'…');realEstateMeshWorkflowRender();
  try{return await action();}
  catch(error){realEstateMeshWorkflowMessage(error?.message||String(error),true);return null;}
  finally{realEstateMeshWorkflow.busy=false;realEstateMeshWorkflowRender();}
}
function realEstateMeshWorkflowRender(){
  const dialog=document.getElementById('real-estate-mesh-dialog');
  if(!dialog||!realEstateMeshWorkflow.slug)return;
  const {row,part}=realEstateMeshWorkflowCurrent();
  if(!row){dialog.close();return;}
  const rig=row.rigAssets?.[part]||{};
  const texture=row.textures?.[part]||{};
  const published=Boolean(rig.assetId);
  // Model publication hashes are fingerprints, not the raw source FBX SHA.
  // Compare to the same canonical value used by RealEstateStore and Studio Sync.
  const current=published && rig.publishedSha256===row.rigPublicationHashes?.[part];
  const syncReady=current && row.status==='PUBLISHED';
  const authored=row.meshSources?.[part];
  const busy=realEstateMeshWorkflow.busy||realEstateMeshWorkflow.atlas.busy||
    realEstatePublicationBusy(row.slug)||realEstateState.atlasBusy;
  const tabs=[{id:'model',label:'Model · FBX'},{id:'texture',label:'Texture · atlas'},
    {id:'lod1',label:'LOD1 · FBX'}];
  const model=window.game1AssetWorkflowDialog.step('Model · FBX',
    'Replace the FBX of this mesh only. Other models and images stay unchanged.',
    `<small class="deco-manage-value">${esc(row.meshSources?.[part]?'Independent FBX revision':'Original house FBX')}</small>`+
    `<div class="shared-model-state"><small>Roblox Model ID: <strong>${esc(rig.assetId||'Not published')}</strong></small>`+
    `<small> · Source: ${esc(authored?.path?'Independent mesh FBX':'Original house FBX')}</small></div>`+
    `<div class="actions"><button type="button" data-mw-replace ${busy?'disabled':''}>Choose replacement FBX</button>`+
    `<button type="button" data-mw-publish ${busy||!realEstateState.data?.publication?.configured||current?'disabled':''}>Publish changed Model</button></div>`,
    current?'Published':'Publication required',current?'ready':'pending');
  const atlas=window.game1ConsumerAtlasEditor.render(realEstateMeshWorkflow.atlas,{
    currentId:texture.atlasVariantId||0,
    linked:texture.atlasOptions||texture.atlasVariants||[],
    catalog:realEstateState.data?.atlasCatalog||[],busy});
  const lod=row.partLod1?.[part]||{status:'NOT_REGISTERED',revision:0};
  const lodName=`${row.slug}_${part}_lod1.fbx`;
  const lodStatus=lod.status||'NOT_REGISTERED';
  const lodEditor=window.game1AssetWorkflowDialog.step('LOD1 · геометрия части',
    'Отдельный упрощённый FBX для этой части. Дистанции и режим задаются в LOD Manager.',
    `<div class="shared-model-state"><small>Статус: <strong>${esc(lodStatus)}</strong></small>`+
    `<small> · Model ID: <strong>${esc(lod.modelAssetId||'—')}</strong></small>`+
    `${lod.reuse?`<small> · Reuse: ${esc(lod.reuse.domain+'/'+lod.reuse.slug)}</small>`:''}</div>`+
    `<p class="hint">Имя FBX: <code>${esc(lodName)}</code></p>`+
    `<div class="actions"><button type="button" data-mw-lod-choose ${busy?'disabled':''}>Выбрать LOD1 FBX</button>`+
    `<button type="button" data-mw-lod-stage ${busy||!realEstateMeshWorkflow.lodSource?'disabled':''}>Сохранить FBX</button>`+
    `<button type="button" data-mw-lod-reuse ${busy?'disabled':''}>Использовать опубликованный LOD1</button>`+
    `<button type="button" data-mw-lod-publish ${busy||!['STAGED','UPDATE_AVAILABLE'].includes(lodStatus)?'disabled':''}>Опубликовать LOD1</button></div>`+
    `${realEstateMeshWorkflow.lodSource?`<small class="deco-manage-value">Выбран: ${esc(realEstateMeshWorkflow.lodSource)}</small>`:''}`,
    lodStatus==='PUBLISHED'?'Опубликован':'LOD1 не готов',lodStatus==='PUBLISHED'?'ready':'pending');
  const footer=window.game1AssetWorkflowDialog.step('Studio Sync',
    'Explicitly synchronize this mesh Model and Atlas to ServerStorage and managed placed houses. This action is independent of the editor tab.',
    `<div class="actions"><button type="button" data-mw-sync ${busy||!syncReady?'disabled':''}>Sync Model + Atlas · Studio</button></div>`,
    !current?'Publish Model first':syncReady?'Ready':'Finish publishing remaining house assets',
    syncReady?'ready':'pending');
  dialog.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">${esc(row.slug)} · mesh</small>`+
    `<h3>${esc(part)}</h3></div><button type="button" data-mw-close aria-label="Close">✕</button></div>`+
    `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">`+
    window.game1AssetWorkflowDialog.tabs(tabs,realEstateMeshWorkflow.tab)+
    `${realEstateMeshWorkflow.tab==='model'?model:realEstateMeshWorkflow.tab==='texture'?atlas:lodEditor}`+
    `${realEstateMeshWorkflow.tab==='lod1'?'':footer}`+
    `<div class="real-estate-workflow-result ${realEstateMeshWorkflow.error?'issue':''}" role="status" ${realEstateMeshWorkflow.result?'':'hidden'}>${esc(realEstateMeshWorkflow.result)}</div></div>`;
  dialog.querySelector('[data-mw-close]').onclick=()=>{if(!busy)dialog.close();};
  dialog.querySelectorAll('[data-mw-tab]').forEach(button=>button.onclick=()=>{
    if(!busy){realEstateMeshWorkflow.tab=button.dataset.mwTab;realEstateMeshWorkflowRender();}
  });
  const bind=(key,handler)=>{const button=dialog.querySelector(`[data-mw-${key}]`);if(button)button.onclick=handler;};
  bind('replace',()=>realEstateMeshWorkflowRun('Replacing FBX',async()=>{
    const saved=await realEstateReplaceMesh(row,part);
    realEstateMeshWorkflowMessage(saved?'FBX revision saved for '+part+'. Publish this Model before Studio Sync.':
      'No FBX revision was saved. Check the source selection.');
  }));
  bind('publish',()=>realEstateMeshWorkflowRun('Starting Model publication',async()=>{
    const fresh=realEstateMeshWorkflowCurrent().row;
    if(!fresh || !fresh.meshParts?.includes(part))throw new Error('Mesh selection changed; refresh the house');
    if(fresh.rigAssets?.[part]?.publishedSha256===fresh.rigPublicationHashes?.[part]){
      realEstateMeshWorkflowMessage('This mesh publication is already current. Studio Sync is available.');
      return;
    }
    if(realEstateState.selected!==row.slug)throw new Error('Selected house changed; reopen Manage Mesh');
    const result=await realEstatePublish('model:'+part);
    realEstateMeshWorkflowMessage(result?'Publishing '+part+' · Studio Sync unlocks after the new Model ID is confirmed.':
      'Model publication did not start. Inspect the publication panel.',!result);
  }));
  bind('sync',()=>realEstateMeshWorkflowRun('Synchronizing Model and Atlas',async()=>{
    const result=await realEstateSync(row.slug,part,{throwOnError:true});
    const stats=result?.studio?.realEstateStats||{};
    const found=Number(stats.workspaceModelsFound||0);
    const updated=Number(stats.workspaceModelsUpdated||0);
    const warnings=stats.rigWarnings||[];
    const incomplete=found===0||updated<found||warnings.length>0;
    realEstateMeshWorkflowMessage((incomplete?'Studio template updated; placed-house Sync incomplete':'Studio Sync complete')+
      ` · placed houses ${updated}/${found}`+
      (found===0?' · no managed house instances found':'')+
      (warnings.length?` · ${warnings.join(' | ')}`:''),incomplete);
  }));
  if(realEstateMeshWorkflow.tab==='lod1'){
    const endpoint=`/api/real-estate/${encodeURIComponent(row.slug)}/parts/${encodeURIComponent(part)}`;
    bind('lod-choose',()=>realEstateMeshWorkflowRun('Выбираем LOD1 FBX',async()=>{
      const selected=await request('/api/files/choose-real-estate-model',{method:'POST'});
      if(!selected?.path){realEstateMeshWorkflowMessage('Выбор отменён');return;}
      const name=selected.path.replace(/\\/g,'/').split('/').pop();
      if(name!==lodName)throw Error(`Имя файла должно быть ${lodName}`);
      realEstateMeshWorkflow.lodSource=selected.path;
      realEstateMeshWorkflowMessage(`LOD1 FBX выбран: ${name}`);
    }));
    bind('lod-stage',()=>realEstateMeshWorkflowRun('Сохраняем LOD1 FBX',async()=>{
      if(!realEstateMeshWorkflow.lodSource)throw Error('Сначала выбери LOD1 FBX');
      await request(endpoint+'/lod1-stage',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({sourcePath:realEstateMeshWorkflow.lodSource,expectedRevision:lod.revision})});
      realEstateMeshWorkflow.lodSource='';
      await realEstateLoad();
      realEstateMeshWorkflowMessage('LOD1 FBX сохранён. Теперь можно опубликовать.');
    }));
    bind('lod-reuse',()=>realEstateMeshWorkflowRun('Выбираем опубликованный LOD1',async()=>{
      const choice=await window.game1LodReusePicker.pick('house_part',row.slug+'/'+part);
      if(!choice){realEstateMeshWorkflowMessage('Выбор отменён');return;}
      await request(endpoint+'/lod1-reuse',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(window.game1LodReusePicker.payload(choice,lod.revision))});
      realEstateMeshWorkflow.lodSource='';
      await realEstateLoad();
      realEstateMeshWorkflowMessage('Опубликованная геометрия LOD1 назначена.');
    }));
    bind('lod-publish',()=>realEstateMeshWorkflowRun('Публикуем LOD1',async()=>{
      await request(endpoint+'/lod1-publish',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({expectedRevision:lod.revision,description:`Game1 ${row.slug}/${part} part LOD1`})});
      await realEstateLoad();
      realEstateMeshWorkflowMessage('LOD1 опубликован. Настрой дистанции в LOD Manager.');
    }));
  }
  if(realEstateMeshWorkflow.tab==='texture'){
    window.game1ConsumerAtlasEditor.wire(dialog,realEstateMeshWorkflow.atlas,{
      consumerType:'real_estate',slug:row.slug,part,
      revision:texture.atlasBindingRevision||0,busy:realEstateMeshWorkflow.busy,
      getRevision:()=>realEstateMeshWorkflowCurrent().row?.textures?.[part]?.atlasBindingRevision||0,
      getCurrentId:()=>realEstateMeshWorkflowCurrent().row?.textures?.[part]?.atlasVariantId||0,
      catalog:realEstateState.data?.atlasCatalog||[],
      filePicker:'/api/files/choose-real-estate-texture',
      onMessage:realEstateMeshWorkflowMessage,onRender:realEstateMeshWorkflowRender,
      onRefresh:realEstateLoad,
    });
  }
}
