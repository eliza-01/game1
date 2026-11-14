/* M234 · Real Estate mesh editor. Uses the SAME consumer atlas editor as
 * Location Assets; Real Estate retains house-specific Model publication/Sync.
 */
const realEstateMeshWorkflow={slug:'',part:'',tab:'model',busy:false,result:'',error:false,
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
  realEstateMeshWorkflow.tab=tab;
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
  const current=published && rig.publishedSha256===row.rigSourceHashes?.[part];
  const busy=realEstateMeshWorkflow.busy||realEstateMeshWorkflow.atlas.busy||
    realEstatePublicationBusy(row.slug)||realEstateState.atlasBusy;
  const tabs=[{id:'model',label:'Model · FBX'},{id:'texture',label:'Texture · atlas'}];
  const model=window.game1AssetWorkflowDialog.step('Model · FBX',
    'Replace the FBX of this mesh only. Other models and images stay unchanged.',
    `<small class="deco-manage-value">${esc(row.meshSources?.[part]?'Independent FBX revision':'Original house FBX')}</small>`+
    `<div class="shared-model-state"><small>Roblox Model ID: <strong>${esc(rig.assetId||'Not published')}</strong></small></div>`+
    `<div class="actions"><button type="button" data-mw-replace ${busy?'disabled':''}>Choose replacement FBX</button>`+
    `<button type="button" data-mw-publish ${busy||!realEstateState.data?.publication?.configured||current?'disabled':''}>Publish changed Model</button></div>`,
    current?'Published':'Publication required',current?'ready':'pending');
  const atlas=window.game1ConsumerAtlasEditor.render(realEstateMeshWorkflow.atlas,{
    currentId:texture.atlasVariantId||0,
    linked:texture.atlasOptions||texture.atlasVariants||[],
    catalog:realEstateState.data?.atlasCatalog||[],busy});
  const footer=window.game1AssetWorkflowDialog.step('Studio Sync',
    'Explicitly synchronize this mesh Model and Atlas to ServerStorage and managed placed houses. This action is independent of the editor tab.',
    `<div class="actions"><button type="button" data-mw-sync ${busy||!current?'disabled':''}>Sync Model + Atlas · Studio</button></div>`,
    current?'Ready':'Publish Model first',current?'ready':'pending');
  dialog.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">${esc(row.slug)} · mesh</small>`+
    `<h3>${esc(part)}</h3></div><button type="button" data-mw-close aria-label="Close">✕</button></div>`+
    `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">`+
    window.game1AssetWorkflowDialog.tabs(tabs,realEstateMeshWorkflow.tab)+
    `${realEstateMeshWorkflow.tab==='model'?model:atlas}${footer}`+
    `<div class="real-estate-workflow-result ${realEstateMeshWorkflow.error?'issue':''}" role="status" ${realEstateMeshWorkflow.result?'':'hidden'}>${esc(realEstateMeshWorkflow.result)}</div></div>`;
  dialog.querySelector('[data-mw-close]').onclick=()=>{if(!busy)dialog.close();};
  dialog.querySelectorAll('[data-mw-tab]').forEach(button=>button.onclick=()=>{
    if(!busy){realEstateMeshWorkflow.tab=button.dataset.mwTab;realEstateMeshWorkflowRender();}
  });
  const bind=(key,handler)=>{const button=dialog.querySelector(`[data-mw-${key}]`);if(button)button.onclick=handler;};
  bind('replace',()=>realEstateMeshWorkflowRun('Replacing FBX',async()=>{
    const saved=await realEstateReplaceMesh(row,part);
    realEstateMeshWorkflowMessage(saved?'FBX revision saved. Publish changed Model before Studio Sync.':
      'No FBX revision was saved. Check the source selection.');
  }));
  bind('publish',()=>realEstateMeshWorkflowRun('Starting Model publication',async()=>{
    realEstateForm(realEstateRows().find(item=>item.slug===row.slug));
    const result=await realEstatePublish('model:'+part);
    realEstateMeshWorkflowMessage(result?'Model publication started. Review publication status before Studio Sync.':
      'Model publication did not start. Inspect the publication panel.',!result);
  }));
  bind('sync',()=>realEstateMeshWorkflowRun('Synchronizing Model and Atlas',async()=>{
    const result=await realEstateSync(row.slug,part,{throwOnError:true});
    const stats=result?.studio?.realEstateStats||{};
    realEstateMeshWorkflowMessage(`Studio Sync complete · placed houses ${Number(stats.workspaceModelsUpdated||0)}/${Number(stats.workspaceModelsFound||0)}`+
      ((stats.rigWarnings||[]).length?` · ${stats.rigWarnings.join(' | ')}`:''),Boolean((stats.rigWarnings||[]).length));
  }));
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
