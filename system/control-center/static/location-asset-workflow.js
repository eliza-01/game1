/* M234 · Location Assets editor. Published Model and shared Atlas remain independent.
 * Atlas presentation/selection is the SAME consumer editor as Real Estate.
 */
window.game1LocationAssetWorkflow = (() => {
  const state={slug:'',tab:'model',busy:false,result:'',error:false,
    pendingModel:'',inspection:null,meshOptions:{},physicsDirty:false,
    atlas:window.game1ConsumerAtlasEditor.newState()};
  const shell=window.game1AssetWorkflowDialog;
  const e=value=>esc(String(value??''));
  const row=()=>decoAssetRow(state.slug);
  const button=(action,label,disabled=false,css='')=>
    `<button type="button" class="${css}" data-la-action="${action}" ${disabled?'disabled':''}>${label}</button>`;
  const dialog=()=>shell.ensure('location-asset-edit-dialog','Manage Location Asset',()=>{
    state.slug='';state.pendingModel='';state.atlas=window.game1ConsumerAtlasEditor.newState();
  });
  const close=()=>{const d=document.getElementById('location-asset-edit-dialog');if(d?.open)d.close();};
  function open(slug){
    const item=decoAssetRow(slug);
    if(!item)return toast('Location Asset no longer exists; refresh.',true);
    if(state.busy)return toast('Finish the current operation first.',true);
    const d=dialog();if(d.open && state.slug!==slug)d.close();
    state.slug=slug;state.tab='model';state.busy=false;state.pendingModel='';
    state.inspection=item.fbxAnalysis||null;
    state.meshOptions=window.game1MeshAuthoring.seeded(state.inspection,item.meshOptions||{});
    state.physicsDirty=false;state.atlas=window.game1ConsumerAtlasEditor.newState();
    message('');render();if(!d.open)d.showModal();
    decoAssetShowSyncHistory(slug);
  }
  function message(text,isError=false){state.result=String(text||'');state.error=Boolean(isError);}
  async function run(label,task){
    if(state.busy)return;
    state.busy=true;message(`${label}…`);render();
    try{return await task();}
    catch(error){message(error?.message||String(error),true);return null;}
    finally{state.busy=false;render();}
  }
  function render(){
    const d=document.getElementById('location-asset-edit-dialog');
    if(!d||!state.slug)return;
    const item=row();if(!item){close();return;}
    const busy=state.busy||state.atlas.busy||decoAssetState.atlasBusy||Boolean(decoAssetState.syncingSlug);
    const configured=Boolean(decoAssetState.data?.publication?.configured);
    const modelCurrent=Boolean(item.model_asset_id&&item.model_sha256===item.model_published_sha256);
    const changed=Boolean(state.pendingModel||state.physicsDirty);
    const needsPublication=Boolean(state.pendingModel||!modelCurrent);
    const publicationReady=Boolean(configured&&(state.pendingModel||item.model_path));
    const tabs=[{id:'identity',label:'Identity'},{id:'model',label:'Model · FBX'},
      {id:'atlas',label:'Texture · atlas'}];
    const card=(name,description,content,status='',css='ready')=>shell.step(name,description,content,status,css);
    const identity=card('Registration details','Metadata changes never publish assets or modify Studio.',
      `<div class="deco-manage-fields"><label>Name<input data-la-name maxlength="120" value="${e(item.name_en)}"></label>`+
      `<label>Slug<input readonly value="${e(item.slug)}"></label>`+
      `<label>Category<select data-la-category>${(decoAssetState.data?.options?.categories||[]).map(c=>
        `<option value="${e(c.id)}" ${c.id===item.category?'selected':''}>${e(c.label)}</option>`).join('')}</select></label>`+
      `<label class="deco-policy-toggle"><input type="checkbox" data-la-destructible ${item.destructible?'checked':''}> Destructible</label></div>`+
      `<div class="actions">${button('save-identity','Apply Changes',busy)}${button('delete','Retire asset',busy)}</div>`,
      `Revision ${Number(item.revision||0)}`);
    const inspection=state.inspection;
    const model=card('Model · FBX',
      'Review mesh names, skeleton and collision settings. A changed FBX is published as a NEW Model ID; physics-only changes do not publish.',
      `<small class="deco-manage-value">${e(state.pendingModel||item.model_path||'No FBX selected')}</small>`+
      window.game1MeshAuthoring.inspectionView(inspection,state.meshOptions)+
      `<div class="actions">${button('choose-fbx','Choose FBX',busy)}${button('inspect-fbx','Analyze saved FBX',busy||!item.model_path)}</div>`+
      `<div class="shared-model-state"><small>Roblox Model ID: <strong>${e(item.model_asset_id||'Not published')}</strong></small>`+
      `<small>${modelCurrent?'Current FBX revision is published.': 'Publication required for current FBX revision.'}</small></div>`+
      `<div class="actions">${button('apply-model',needsPublication?'Publish and Apply':'Apply Changes',
        busy||(!changed&&!needsPublication)||(needsPublication&&!publicationReady),
        changed||needsPublication?'asset-apply-ready':'')}</div>`,
      modelCurrent?'Published':'Changes pending',modelCurrent?'ready':'pending');
    const atlas=window.game1ConsumerAtlasEditor.render(state.atlas,{
      currentId:item.atlasVariantId||0,linked:item.atlasVariants||[],
      catalog:decoAssetState.data?.atlases||[],busy});
    const footer=card('Studio Sync',
      'One explicit command for this Location Asset. Synchronizes its published Model and Atlas to managed placed instances. No other slug is affected.',
      `<div class="actions">${button('sync','Sync Model + Atlas · Studio',busy||item.status!=='PUBLISHED')}</div>`,
      item.status==='PUBLISHED'?'Ready':'Publish Model and Atlas first',
      item.status==='PUBLISHED'?'ready':'pending');
    d.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">Location Asset · ${e(item.slug)}</small>`+
      `<h3>Manage ${e(item.name_en)}</h3></div><button type="button" data-la-close aria-label="Close">✕</button></div>`+
      `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">${shell.tabs(tabs,state.tab,'data-la-tab')}`+
      `${state.tab==='identity'?identity:state.tab==='model'?model:atlas}${footer}`+
      `<div class="real-estate-workflow-result ${state.error?'issue':''}" role="status" ${state.result?'':'hidden'}>${e(state.result)}</div></div>`;
    if(state.tab==='model')window.game1MeshAuthoring.wire(d,state.meshOptions,()=>{
      state.physicsDirty=true;
      const apply=d.querySelector('[data-la-action="apply-model"]');
      if(apply){apply.disabled=false;apply.classList.add('asset-apply-ready');}
    },Boolean(inspection?.hasCollider));
    d.querySelector('[data-la-close]').onclick=()=>{if(!busy)d.close();};
    d.querySelectorAll('[data-la-tab]').forEach(b=>b.onclick=()=>{if(!busy){state.tab=b.dataset.laTab;render();}});
    d.querySelectorAll('[data-la-action]').forEach(b=>b.onclick=()=>execute(b.dataset.laAction));
    if(state.tab==='atlas')window.game1ConsumerAtlasEditor.wire(d,state.atlas,{
      consumerType:'location_asset',slug:state.slug,
      revision:item.bindingRevision||0,busy:state.busy,
      getRevision:()=>row()?.bindingRevision||0,getCurrentId:()=>row()?.atlasVariantId||0,
      catalog:decoAssetState.data?.atlases||[],
      filePicker:'/api/files/choose-location-asset-texture',
      onMessage:message,onRender:render,onRefresh:decoAssetLoad,
    });
  }
  async function execute(action){
    const item=row();if(!item)return;
    if(action==='delete')return decoAssetDelete(state.slug);
    if(action==='save-identity')return run('Applying metadata',async()=>{
      const d=dialog();await decoAssetSaveEdits(state.slug,{
        nameEn:d.querySelector('[data-la-name]').value.trim(),
        category:d.querySelector('[data-la-category]').value,
        destructible:d.querySelector('[data-la-destructible]').checked},item.revision);
      message('Metadata updated. No publication or Studio changes.');
    });
    if(action==='choose-fbx')return run('Inspecting FBX',async()=>{
      const chosen=await request('/api/files/choose-location-asset-model',{method:'POST'});
      if(!chosen?.path){message('FBX selection cancelled.');return;}
      const inspected=await decoAssetInspectSource(chosen.path);
      state.pendingModel=chosen.path;state.inspection=inspected.analysis;
      state.meshOptions=window.game1MeshAuthoring.seeded(inspected.analysis,item.meshOptions||{});
      state.physicsDirty=true;
      message('FBX analyzed. Review changes, then Publish and Apply.');
    });
    if(action==='inspect-fbx')return run('Inspecting saved FBX',async()=>{
      await request(`/api/location-assets/${encodeURIComponent(state.slug)}/inspect-fbx`,{method:'POST'});
      await decoAssetLoad();state.inspection=row()?.fbxAnalysis||null;
      state.meshOptions=window.game1MeshAuthoring.seeded(state.inspection,row()?.meshOptions||{});
      state.physicsDirty=false;message('FBX analysis updated without publication.');
    });
    if(action==='apply-model')return run('Applying Model changes',async()=>{
      const needsSave=Boolean(state.pendingModel||state.physicsDirty);
      if(needsSave){
        await decoAssetSaveEdits(state.slug,{
          ...(state.pendingModel?{modelSourcePath:state.pendingModel}:{}),
          meshOptions:state.meshOptions},item.revision);
        state.pendingModel='';state.physicsDirty=false;
        state.inspection=row()?.fbxAnalysis||state.inspection;
      }
      const current=row();
      if(!current.model_asset_id||current.model_sha256!==current.model_published_sha256){
        const result=await decoAssetPublish(state.slug,'model',false);
        message(`Model published · new ID ${result.model_asset_id}. Atlas ID ${result.texture_asset_id||'—'} unchanged. Use Studio Sync below to update placed instances.`);
      }else message('Mesh settings applied. Published Model ID unchanged. Use Studio Sync below to apply physics in Place.');
    });
    if(action==='sync')return run('Syncing Model + Atlas',async()=>{
      const result=await decoAssetSyncStudio(state.slug,{throwOnError:true});
      message(result?window.game1StudioSync.locationSummary(state.slug,result.studio):'Studio Sync cancelled.');
    });
  }
  return Object.freeze({open,close,render});
})();
