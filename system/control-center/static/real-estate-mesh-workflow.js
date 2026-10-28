/* M143 · Real Estate mesh workflow UI.
 * Presentation and orchestration only. Source revisions, publications, atlas
 * bindings and Studio sync remain owned by their respective services.
 */
const realEstateMeshWorkflow = {slug:'',part:'',tab:'model',busy:false,chosenAtlasId:0,
  sourcePending:false,result:'',error:false};
function realEstateMeshWorkflowEnsure(){
  let dialog=document.getElementById('real-estate-mesh-dialog');
  if(dialog)return dialog;
  dialog=document.createElement('dialog');
  dialog.id='real-estate-mesh-dialog';
  dialog.className='real-estate-mesh-dialog';
  dialog.setAttribute('aria-label','Manage Real Estate mesh');
  dialog.addEventListener('close',()=>{realEstateMeshWorkflow.slug='';realEstateMeshWorkflow.part='';});
  document.body.appendChild(dialog);
  return dialog;
}
function realEstateMeshWorkflowCurrent(){
  const row=realEstateRows().find(item=>item.slug===realEstateMeshWorkflow.slug);
  return {row,part:realEstateMeshWorkflow.part};
}
function realEstateMeshWorkflowOpen(slug,part,tab='model'){
  const row=realEstateRows().find(item=>item.slug===slug);
  if(!row||(row.meshParts||[]).indexOf(part)<0)return;
  realEstateMeshWorkflow.slug=slug;
  realEstateMeshWorkflow.part=part;
  realEstateMeshWorkflow.tab=realEstateIsCollider(part)?'model':tab;
  realEstateMeshWorkflow.sourcePending=false;
  realEstateMeshWorkflow.chosenAtlasId=Number(row.textures?.[part]?.atlasVariantId||0);
  realEstateMeshWorkflow.result='';realEstateMeshWorkflow.error=false;
  realEstateForm(row); // The register form uses this house, never the previous selection.
  const dialog=realEstateMeshWorkflowEnsure();
  realEstateMeshWorkflowRender();
  if(!dialog.open)dialog.showModal();
}
function realEstateMeshWorkflowMessage(message,error=false){
  realEstateMeshWorkflow.result=String(message||'');
  realEstateMeshWorkflow.error=Boolean(error);
  realEstateMeshWorkflowRender();
}
async function realEstateMeshWorkflowRun(label,action){
  if(realEstateMeshWorkflow.busy)return;
  realEstateMeshWorkflow.busy=true;
  realEstateMeshWorkflowMessage(label+'…');
  try{
    const result=await action();
    return result;
  }catch(error){
    const message=error?.message||String(error);
    realEstateMeshWorkflowMessage(message,true);
    toast(message,true);
    return null;
  }finally{
    realEstateMeshWorkflow.busy=false;
    realEstateMeshWorkflowRender();
  }
}
function realEstateMeshWorkflowRender(){
  const dialog=document.getElementById('real-estate-mesh-dialog');
  if(!dialog||!realEstateMeshWorkflow.slug)return;
  const {row,part}=realEstateMeshWorkflowCurrent();
  if(!row){dialog.close();return;}
  const collider=realEstateIsCollider(part);
  const rig=row.rigAssets?.[part]||{};
  const texture=row.textures?.[part]||{};
  const published=Boolean(rig.assetId);
  const current=published && rig.publishedSha256===row.rigSourceHashes?.[part];
  const publication=realEstatePublicationBusy(row.slug);
  const busy=realEstateMeshWorkflow.busy||publication||realEstateState.atlasBusy;
  const canPublish=Boolean(realEstateState.data?.publication?.configured);
  const job=realEstateState.publicationJob;
  const meshJob=job?.slug===row.slug && String(job.scope||'')===`model:${part}`?job:null;
  const imageJob=job?.slug===row.slug && String(job.scope||'')===`image:${part}`?job:null;
  const modelStatus=meshJob&&(meshJob.status==='running'||meshJob.status==='queued')
    ? `Publishing · ${meshJob.step||meshJob.status}`
    : current?`Published · Model ID ${rig.assetId}`:published?'Changed · new Model ID required':'Not published';
  const modelClass=current?'ready':'pending';
  const sourceText=row.meshSources?.[part]?'Independent FBX revision':'Original house FBX';
  const activeVariant=Number(texture.atlasVariantId||0);
  const atlasChoices=realEstatePublishedAtlasChoices();
  const activeAtlas=atlasChoices.find(entry=>entry.reference===`atlas:${activeVariant}`);
  const selectedAtlas=realEstateMeshWorkflow.chosenAtlasId||activeVariant;
  const canSync=current&&!busy;
  const modelTab=realEstateMeshWorkflow.tab==='model';
  const isReused=Boolean(texture.reuseReference||activeVariant);
  const imageReady=Boolean(row.publicationCurrent?.[part] && (texture.assetId||isReused));
  dialog.innerHTML=`<div class="real-estate-mesh-dialog-head">
      <div><small class="eyebrow">${esc(row.slug)} · mesh</small><h3>${esc(part)}${collider?' · collision':''}</h3></div>
      <button type="button" data-mw-close aria-label="Close mesh workflow">✕</button>
    </div><div class="real-estate-mesh-dialog-body" aria-busy="${busy}">
      <nav class="real-estate-mesh-tabs" aria-label="Mesh operations">
        <button type="button" data-mw-tab="model" aria-selected="${modelTab}">Model · FBX</button>
        ${collider?'':`<button type="button" data-mw-tab="texture" aria-selected="${!modelTab}">Texture · atlas</button>`}
      </nav>
      ${modelTab?`<section class="real-estate-mesh-step">
        <div class="real-estate-mesh-step-head"><strong>1 · Source FBX</strong><span class="real-estate-step-status ready">${esc(sourceText)}</span></div>
        <p>Replace only ${esc(part)}. A standalone FBX or the matching mesh from a full-house FBX is accepted. Other models and images stay unchanged.</p>
        <div class="actions"><button type="button" data-mw-replace ${busy?'disabled':''}>Choose replacement FBX</button></div>
      </section>
      <section class="real-estate-mesh-step">
        <div class="real-estate-mesh-step-head"><strong>2 · Roblox Model</strong><span class="real-estate-step-status ${modelClass}">${esc(modelStatus)}</span></div>
        <p>${current?'The currently registered FBX is published.': 'Publish the selected revision to get a NEW Model Asset ID. The old ID remains active until publication succeeds.'}</p>
        <div class="actions"><button type="button" data-mw-publish ${busy||!canPublish?'disabled':''}>${current?'Republish model · new ID':'Publish changed model'}</button></div>
        ${meshJob?.status==='failed'?`<small class="real-estate-step-status issue">${esc(meshJob.error||'Publication failed')}</small>`:''}
      </section>
      <section class="real-estate-mesh-step">
        <div class="real-estate-mesh-step-head"><strong>3 · Studio Sync</strong><span class="real-estate-step-status ${current?'ready':'pending'}">${current?'Ready':'Publish model first'}</span></div>
        <p>Updates this mesh in ServerStorage and every managed placed house tagged Game1RealEstateSlug. Untagged copies are not modified.</p>
        <div class="actions"><button type="button" data-mw-sync ${!canSync?'disabled':''}>Sync model · template + placed</button></div>
      </section>`:`<section class="real-estate-mesh-step">
        <div class="real-estate-mesh-step-head"><strong>Current atlas</strong><span class="real-estate-step-status ${imageReady?'ready':'pending'}">${imageReady?'Published':'Not ready'}</span></div>
        <p>${esc(texture.filename||texture.reuseReference||'No texture selected')} · ${texture.assetId?'Image ID '+esc(texture.assetId):isReused?'Shared reference · existing published ID':'No Image ID'}</p>
      </section>
      <section class="real-estate-mesh-step">
        <strong>Use an existing published atlas</strong>
        <p>Changes this mesh binding to the existing Roblox Image ID and attempts Studio Sync. No upload or publication.</p>
        <select data-mw-atlas aria-label="Choose published atlas">
          <option value="">Select a published atlas…</option>
          ${atlasChoices.map(a=>`<option value="${esc(a.reference)}" ${a.reference===`atlas:${selectedAtlas}`?'selected':''}>${esc(a.filename||a.label)} · ${esc(a.assetId)}</option>`).join('')}
        </select>
        <div class="actions"><button type="button" data-mw-use-atlas ${busy||!selectedAtlas||selectedAtlas===activeVariant?'disabled':''}>Use existing atlas · no upload</button></div>
      </section>
      ${activeVariant?`<section class="real-estate-mesh-step">
        <strong>Republish the current atlas</strong>
        <p>Upload changed pixels for the same version and resolution. Roblox creates a NEW Image Asset ID; all consumers of this variant receive the new ID.</p>
        <div class="actions"><button type="button" data-mw-republish-atlas ${busy||!canPublish?'disabled':''}>Republish atlas · new Image ID</button></div>
      </section>`:''}
      <section class="real-estate-mesh-step">
        <strong>Choose a new local texture</strong>
        <p>Choosing a file does not publish it. Save it to the registry first; publish a new Image ID only when needed.</p>
        <div class="actions"><button type="button" data-mw-local ${busy?'disabled':''}>Choose image</button>
          <button type="button" data-mw-save-image ${busy||!realEstateMeshWorkflow.sourcePending?'disabled':''}>Save image source</button></div>
        ${realEstateMeshWorkflow.sourcePending?`<small class="real-estate-step-status pending">Selected: ${esc(realEstateState.textures[part]||'')} · not yet saved</small>`:''}
      </section>
      <section class="real-estate-mesh-step">
        <strong>Publish image / Sync</strong>
        <p>Changed image bytes require a NEW Image Asset ID. An unchanged/reused published atlas needs no upload.</p>
        <div class="actions"><button type="button" data-mw-publish-image ${busy||!canPublish||imageReady||isReused?'disabled':''}>Publish changed image</button>
          <button type="button" data-mw-sync-texture ${busy||!imageReady?'disabled':''}>Sync texture · Studio</button></div>
        ${imageJob?.status==='running'||imageJob?.status==='queued'?`<small>Publishing · ${esc(imageJob.step||imageJob.status)}</small>`:''}
      </section>`}
      <div class="real-estate-workflow-result ${realEstateMeshWorkflow.error?'issue':''}" role="status" ${realEstateMeshWorkflow.result?'':'hidden'}>${esc(realEstateMeshWorkflow.result)}</div>
    </div>`;
  dialog.querySelector('[data-mw-close]').onclick=()=>dialog.close();
  for(const tab of dialog.querySelectorAll('[data-mw-tab]')){
    tab.onclick=()=>{realEstateMeshWorkflow.tab=tab.dataset.mwTab;realEstateMeshWorkflowRender();};
  }
  const bind=(name,handler)=>{const button=dialog.querySelector(`[data-mw-${name}]`);if(button)button.onclick=handler;};
  bind('replace',()=>realEstateMeshWorkflowRun('Opening FBX',async()=>{
    const saved=await realEstateReplaceMesh(row,part);
    realEstateMeshWorkflowMessage(saved?'FBX revision saved · next: Publish changed model.':'FBX not replaced · cancelled or failed. See notification for errors.',!saved);
  }));
  bind('publish',()=>realEstateMeshWorkflowRun('Starting model publication',async()=>{
    realEstateForm(realEstateRows().find(item=>item.slug===row.slug));
    const result=await realEstatePublish('model:'+part);
    realEstateMeshWorkflowMessage(result?'Model publication started · progress is shown above. After success, Sync this model.':'Publication could not start. See notification.',!result);
  }));
  bind('sync',()=>realEstateMeshWorkflowRun('Syncing managed houses',async()=>{
    const result=await realEstateSync(row.slug,part);
    if(result){const stats=result.studio?.realEstateStats||{};
      realEstateMeshWorkflowMessage(`Template updated · placed houses ${Number(stats.workspaceModelsUpdated||0)}/${Number(stats.workspaceModelsFound||0)}${(stats.rigWarnings||[]).length?' · warnings: '+stats.rigWarnings.join(' | '):''}`,Boolean((stats.rigWarnings||[]).length));}
    else realEstateMeshWorkflowMessage('Studio Sync failed · see notification.',true);
  }));
  // Atlas inputs only exist in the texture tab. The model tab has no picker.
  if(!collider && !modelTab){
    const picker=dialog.querySelector('[data-mw-atlas]');
    if(picker)picker.onchange=()=>{realEstateMeshWorkflow.chosenAtlasId=Number(String(picker.value).split(':')[1]||0);realEstateMeshWorkflowRender();};
    bind('use-atlas',()=>realEstateMeshWorkflowRun('Applying existing atlas',async()=>{
      if(!realEstateMeshWorkflow.chosenAtlasId)throw Error('Choose a published atlas');
      const changed=await realEstateChooseAtlas(row,part,realEstateMeshWorkflow.chosenAtlasId);
      if(changed){realEstateMeshWorkflow.sourcePending=false;
        realEstateMeshWorkflowMessage(changed.studioSyncStatus==='pending_studio_sync'
          ? 'Atlas binding saved · Studio Sync pending. Retry after Studio connects.'
          : 'Existing Image Asset ID selected · no upload · Studio updated.',
          changed.studioSyncStatus==='pending_studio_sync');}
    }));
    bind('republish-atlas',()=>realEstateMeshWorkflowRun('Preparing atlas republish',async()=>{
      const variant=(texture.atlasVariants||[]).find(v=>Number(v.id)===activeVariant);
      if(!variant)throw Error('Current atlas variant not available; refresh the catalog');
      const published=await realEstateRepublishAtlas(variant);
      realEstateMeshWorkflowMessage(published
        ? (published.unchanged?'Image unchanged · no new upload.':'Atlas republished · new Image ID '+(published.variant?.published_id||'—'))
        : 'Atlas republish cancelled or failed · no confirmed new Image ID.',!published);
    }));
    bind('local',()=>realEstateMeshWorkflowRun('Opening image chooser',async()=>{
      realEstateForm(realEstateRows().find(item=>item.slug===row.slug));
      const chosen=await realEstateBrowseTexture(part);
      if(chosen){realEstateMeshWorkflow.sourcePending=true;
        realEstateMeshWorkflowMessage('Image selected locally · next: Save image source. No Roblox upload yet.');}
    }));
    bind('save-image',()=>realEstateMeshWorkflowRun('Saving image source',async()=>{
      const saved=await realEstateRegister();
      if(saved){realEstateMeshWorkflow.sourcePending=false;
        realEstateMeshWorkflowMessage('Image source saved · if Image Asset is changed, publish it next.');}
      else realEstateMeshWorkflowMessage('Image source was not saved · see notification.',true);
    }));
    bind('publish-image',()=>realEstateMeshWorkflowRun('Starting image publication',async()=>{
      realEstateForm(realEstateRows().find(item=>item.slug===row.slug));
      const result=await realEstatePublish('image:'+part);
      realEstateMeshWorkflowMessage(result?'Image publication started · Roblox assigns a new ID on changed bytes.':'Image publication could not start · see notification.',!result);
    }));
    bind('sync-texture',()=>realEstateMeshWorkflowRun('Syncing texture',async()=>{
      const result=await realEstateSync(row.slug,part);
      if(result){const stats=result.studio?.realEstateStats||{};
        realEstateMeshWorkflowMessage(`Studio updated · placed houses ${Number(stats.workspaceModelsUpdated||0)}/${Number(stats.workspaceModelsFound||0)}`);}
      else realEstateMeshWorkflowMessage('Texture Studio Sync failed · see notification.',true);
    }));
  }
}
