/* Location Asset editor M220.
 * Real resource workflow, NOT a relocated registration form. Model revisions,
 * shared atlas publications and scoped Studio IDs are independent operations.
 * Real Estate shares the step/tab shell and Atlas Registry transport.
 */
window.game1LocationAssetWorkflow = (() => {
  const state = {
    slug:'',tab:'model',busy:false,selectedAtlasId:0,atlasSearch:'',
    pendingModel:'',pendingNewAtlas:'',pendingRepublishAtlas:'',result:'',error:false,
  };
  const shell = window.game1AssetWorkflowDialog;
  const atlas = window.game1AtlasWorkflow;
  const e = value => esc(String(value ?? ''));
  const row = () => decoAssetRow(state.slug);
  const buttons = (action, label, disabled=false) => `<button type="button" data-la-action="${action}" ${disabled?'disabled':''}>${label}</button>`;
  function dialog() {
    return shell.ensure('location-asset-edit-dialog', 'Manage Location Asset', () => {
      state.slug='';state.pendingModel='';state.pendingNewAtlas='';state.pendingRepublishAtlas='';
    });
  }
  function close() { const d = document.getElementById('location-asset-edit-dialog');if (d?.open) d.close(); }
  function open(slug) {
    const item = decoAssetRow(slug);
    if (!item) return toast('Location Asset no longer exists; refresh the library.', true);
    if (state.busy) return toast('Finish the current asset operation first.', true);
    const d = dialog();
    if (d.open && state.slug !== slug) d.close();
    state.slug = slug;
    state.tab='model';state.busy=false;state.selectedAtlasId=Number(item.atlasVariantId||0);
    state.atlasSearch='';state.pendingModel='';state.pendingNewAtlas='';state.pendingRepublishAtlas='';
    state.result='';state.error=false;
    render();
    if (!d.open) d.showModal();
    decoAssetShowSyncHistory(slug);
  }
  function message(value, isError=false) {state.result=String(value||'');state.error=Boolean(isError);}
  async function run(label, action) {
    if (state.busy) return;
    state.busy=true;message(`${label}…`);render();
    try {
      const result=await action();
      return result;
    } catch (error) {
      message(error?.message||String(error),true);
      toast(`Location Asset ${state.slug}: ${error?.message||error}`,true);
      return null;
    } finally {state.busy=false;render();}
  }
  function publishedChoices() {
    const search=state.atlasSearch.toLowerCase();
    const matches=[];
    for (const family of decoAssetState.data?.atlases||[]) {
      for (const v of family.variants||[]) {
        if (!v.current || !v.published_id) continue;
        if (search && !`${family.atlasKey} ${v.filename} ${v.resolution} ${v.published_id}`.toLowerCase().includes(search)
            && Number(v.id)!==state.selectedAtlasId) continue;
        matches.push({...v, family:family.atlasKey});
      }
    }
    return matches;
  }
  function render() {
    const d=document.getElementById('location-asset-edit-dialog');
    if (!d||!state.slug) return;
    const item=row();
    if (!item) {close();return;}
    const busy=state.busy||decoAssetState.atlasBusy||Boolean(decoAssetState.syncingSlug);
    const configured=Boolean(decoAssetState.data?.publication?.configured);
    const modelCurrent=Boolean(item.model_asset_id&&item.model_sha256===item.model_published_sha256);
    const atlasCurrent=Boolean(item.texture_asset_id&&item.texture_sha256===item.texture_published_sha256);
    const modelLabel=modelCurrent?`Published · Model ID ${item.model_asset_id}`:
      item.model_asset_id?`Changed · published ID ${item.model_asset_id}`:'Not published';
    const modelStatus=modelCurrent?'ready':'pending';
    const atlasChoices=publishedChoices();
    const currentVariant=Number(item.atlasVariantId||0);
    const selectValue=state.selectedAtlasId||currentVariant;
    const tabs=[{id:'identity',label:'Identity'},{id:'model',label:'Model · FBX'},{id:'atlas',label:'Texture · atlas'}];
    const actionButtons={};
    const card=(title,desc,html,tag='',css='ready')=>shell.step(title,desc,html,tag,css);
    const identity=card('Registration details','Changes to metadata do not publish Roblox assets or touch Studio.',
      `<div class="deco-manage-fields"><label>Asset name<input data-la-name value="${e(item.name_en)}" maxlength="120"></label>`+
      `<label>Slug<input value="${e(item.slug)}" readonly aria-label="Immutable slug"></label>`+
      `<label>Category<select data-la-category>${(decoAssetState.data.options?.categories||[]).map(c=>
        `<option value="${e(c.id)}" ${c.id===item.category?'selected':''}>${e(c.label)}</option>`).join('')}</select></label>`+
      `<label class="deco-policy-toggle"><input data-la-destructible type="checkbox" ${item.destructible?'checked':''}> Destructible</label></div>`+
      `<div class="actions">${buttons('save-identity','Save metadata',busy)}${buttons('delete','Retire asset',busy)}</div>`,
      `Revision ${Number(item.revision||0)}`);
    const model=card('1 · Source FBX',
      'Replace the source of this asset only. All already placed instances remain untouched. Save before publication.',
      `<small class="deco-manage-value">${e(item.model_path||'No FBX source')}</small>`+
      `<div class="actions">${buttons('choose-fbx','Choose replacement FBX',busy)}`+
      `${buttons('save-fbx','Save FBX revision',busy||!state.pendingModel)}</div>`+
      `${state.pendingModel?`<small class="real-estate-step-status pending">Selected: ${e(state.pendingModel)} · not saved</small>`:''}`,
      modelCurrent?'Source published':'New publication required',modelStatus)
      + card('2 · Roblox Model',
        modelCurrent?'The registered FBX is published. Republish explicitly to create a NEW Model ID.':
          'Publish this FBX revision as a NEW Roblox Model ID. The old Model ID stays valid and in the audit history.',
        `<small class="deco-manage-value">${e(modelLabel)}</small><div class="actions">`+
        `${buttons('publish-model',modelCurrent?'Republish Model · new ID':'Publish changed Model',busy||!configured||Boolean(state.pendingModel))}</div>`,
        modelLabel,modelStatus)
      + card('3 · Studio Sync · existing placements',
        'Updates published MeshPart geometry in-place and atlas IDs for all managed placements of THIS slug. ' +
        'Requires matching MeshPart names/layout and a backup Place; mismatches refuse without changes.',
        `<div class="actions">${buttons('sync','Sync Model + Atlas · Studio',busy||item.status!=='PUBLISHED')}</div>`,
        item.status==='PUBLISHED'?'Ready for guarded Sync':'Publish both resources first',item.status==='PUBLISHED'?'ready':'pending');
    const atlasView=card('Current atlas', 'The atlas is an independent shared resource, not owned by this model.',
      `<small class="deco-manage-value">${e(decoAssetTextureFilename(item)||'Not selected')} · `+
      `Image ID ${e(item.texture_asset_id||'not published')}</small>`,
      atlasCurrent?'Published':'Publication required',atlasCurrent?'ready':'pending')
      + card('Use an existing published atlas',
        'Changes the binding for THIS Location Asset. Reuses the existing Image ID; no upload and no automatic Studio Sync.',
        `<label>Search atlas<input type="search" data-la-search value="${e(state.atlasSearch)}" placeholder="name · resolution · ID"></label>`+
        `<select data-la-atlas aria-label="Published atlas variants"><option value="">Choose published atlas…</option>`+
        `${atlasChoices.map(v=>`<option value="${Number(v.id)}" ${Number(v.id)===selectValue?'selected':''}>`+
          `${e(v.filename)} · ${e(v.published_id)}</option>`).join('')}</select>`+
        `<div class="actions">${buttons('use-atlas','Use existing atlas · no upload',busy||!state.selectedAtlasId||state.selectedAtlasId===currentVariant)}</div>`)
      + (currentVariant?card('Republish the current atlas',
        'Select changed pixels with the SAME atlas name and resolution. Roblox creates a NEW Image ID. ' +
        'Every consumer of this shared variant becomes pending; NO Place is modified automatically.',
        `<div class="actions">${buttons('choose-republish','Choose changed image',busy)}`+
        `${buttons('republish','Republish atlas · new Image ID',busy||!configured||!state.pendingRepublishAtlas)}</div>`+
        `${state.pendingRepublishAtlas?`<small class="real-estate-step-status pending">${e(state.pendingRepublishAtlas)} · not uploaded</small>`:''}`):'')
      + card('Choose a new local texture',
        'A new atlas name/resolution is saved to the shared Atlas Registry. It is not uploaded until Publish.',
        `<div class="actions">${buttons('choose-new-image','Choose image',busy)}`+
        `${buttons('save-new-image','Save image source',busy||!state.pendingNewAtlas)}</div>`+
        `${state.pendingNewAtlas?`<small class="real-estate-step-status pending">${e(state.pendingNewAtlas)} · not saved</small>`:''}`)
      + card('Publish image / Sync',
        'Changed atlas pixels require a NEW Image ID. Reused published atlases need no upload. ' +
        'Sync applies Model geometry and Atlas IDs together, only for placed instances of this slug.',
        `<div class="actions">${buttons('publish-image','Publish changed image',busy||!configured||atlasCurrent||!currentVariant)}`+
        `${buttons('sync','Sync Model + Atlas · Studio',busy||item.status!=='PUBLISHED')}</div>`,
        atlasCurrent?'Ready':'Publish atlas first',atlasCurrent?'ready':'pending');
    d.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">Location Asset · ${e(item.slug)}</small>`+
      `<h3>Manage ${e(item.name_en)}</h3></div><button data-la-close type="button" aria-label="Close editor">✕</button></div>`+
      `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">${shell.tabs(tabs,state.tab,'data-la-tab')}`+
      `${state.tab==='identity'?identity:state.tab==='model'?model:atlasView}`+
      `<div class="real-estate-workflow-result ${state.error?'issue':''}" role="status" ${state.result?'':'hidden'}>${e(state.result)}</div></div>`;
    d.querySelector('[data-la-close]').onclick=()=>{if(!state.busy)d.close();};
    d.querySelectorAll('[data-la-tab]').forEach(button=>button.onclick=()=>{
      if(!state.busy){state.tab=button.dataset.laTab;message('');render();}
    });
    d.querySelectorAll('[data-la-action]').forEach(button=>{
      button.onclick=()=>execute(button.dataset.laAction);
    });
    const search=d.querySelector('[data-la-search]');
    if(search)search.oninput=()=>{
      state.atlasSearch=search.value;
      const position=search.selectionStart;
      render();
      const next=d.querySelector('[data-la-search]');
      next?.focus();
      try { next?.setSelectionRange(position,position); } catch {}
    };
    const selection=d.querySelector('[data-la-atlas]');
    if(selection)selection.onchange=()=>{
      state.selectedAtlasId=Number(selection.value||0);render();
    };
  }
  async function execute(action) {
    const item=row();
    if(!item)return;
    if(action==='delete')return decoAssetDelete(state.slug);
    if(action==='save-identity'){
      const d=dialog();
      const name=d.querySelector('[data-la-name]').value.trim();
      const category=d.querySelector('[data-la-category]').value;
      const destructible=d.querySelector('[data-la-destructible]').checked;
      return run('Saving metadata',async()=>{
        await decoAssetSaveEdits(state.slug,{nameEn:name,category,destructible},item.revision);
        message('Metadata saved. Model and atlas publications unchanged.');
      });
    }
    if(action==='choose-fbx')return run('Selecting FBX',async()=>{
      const selected=await request('/api/files/choose-location-asset-model',{method:'POST'});
      if(selected?.path){state.pendingModel=selected.path;message('FBX selected locally · save its revision next.');}
      else message('FBX selection cancelled.');
    });
    if(action==='save-fbx')return run('Saving FBX revision',async()=>{
      await decoAssetSaveEdits(state.slug,{modelSourcePath:state.pendingModel},item.revision);
      state.pendingModel='';message('FBX revision saved. Publish Model to obtain a NEW Model Asset ID.');
    });
    if(action==='publish-model'){
      const force=Boolean(item.model_asset_id&&item.model_sha256===item.model_published_sha256);
      if(force&&!window.confirm(`Republish ${state.slug} model with unchanged FBX? Roblox will create a NEW Model Asset ID.`))return;
      return run('Publishing Roblox Model',async()=>{
        const result=await decoAssetPublish(state.slug,'model',force);
        message(`Model published · ID ${result.model_asset_id}. Previous IDs remain in Database → Asset History.`);
      });
    }
    if(action==='choose-republish'||action==='choose-new-image')return run('Choosing atlas image',async()=>{
      const selected=await atlas.chooseImage('/api/files/choose-location-asset-texture');
      if(selected?.path){
        if(action==='choose-republish')state.pendingRepublishAtlas=selected.path;
        else state.pendingNewAtlas=selected.path;
        message('Image selected · not yet saved or uploaded.');
      }else message('Image selection cancelled.');
    });
    if(action==='save-new-image')return run('Saving atlas source',async()=>{
      await decoAssetSaveEdits(state.slug,{textureSourcePath:state.pendingNewAtlas,atlasVariantId:0},item.revision);
      state.pendingNewAtlas='';state.selectedAtlasId=Number(row()?.atlasVariantId||0);
      message('Atlas source saved. Publish changed image to obtain its Roblox Image ID.');
    });
    if(action==='use-atlas')return run('Binding published atlas',async()=>{
      if(!state.selectedAtlasId)throw Error('Choose a published atlas');
      const changed=await decoAssetChooseAtlasVariant(item,state.selectedAtlasId);
      if(!changed)throw Error('Atlas binding was not saved');
      message('Existing Image ID selected. No publication, no automatic Studio Sync.');
    });
    if(action==='republish'){
      if(!window.confirm(`Republish shared atlas of ${state.slug}? ALL consumers of this atlas variant will get the new Image ID; their Studio instances require separate Sync.`))return;
      return run('Republishing shared atlas',async()=>{
        const result=await atlas.republish(item.atlasVariantId,state.pendingRepublishAtlas);
        state.pendingRepublishAtlas='';
        await decoAssetLoad();
        message(result.unchanged?'Atlas bytes unchanged · existing Image ID kept.':
          `New Image ID ${result.variant?.published_id||'—'} · ${result.pendingConsumers||0} consumer(s) pending explicit Studio Sync.`);
      });
    }
    if(action==='publish-image')return run('Publishing image',async()=>{
      const result=await atlas.publish(item.atlasVariantId);
      await decoAssetLoad();
      message(`Atlas published · Image ID ${result.published_id||'—'}. Sync only the consumers you choose.`);
    });
    if(action==='sync')return run('Syncing Model + Atlas',async()=>{
      const result=await decoAssetSyncStudio(state.slug);
      if(!result)throw Error('Studio Sync failed; see notification');
      message(window.game1StudioSync.locationSummary(state.slug,result.studio));
    });
  }
  return Object.freeze({open,close,render});
})();
