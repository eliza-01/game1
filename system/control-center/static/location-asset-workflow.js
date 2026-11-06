/* M234 · Location Assets editor. Published Model and shared Atlas remain independent.
 * Atlas presentation/selection is the SAME consumer editor as Real Estate.
 */
window.game1LocationAssetWorkflow = (() => {
  const state={slug:'',tab:'model',busy:false,result:'',error:false,manualSlug:false,identityDraft:null,
    pendingModel:'',inspection:null,meshOptions:{},physicsDirty:false,scan:null,scanStale:false,alphaDraft:null,
    atlas:window.game1ConsumerAtlasEditor.newState()};
  const shell=window.game1AssetWorkflowDialog;
  const e=value=>esc(String(value??''));
  const row=()=>decoAssetRow(state.slug);
  const button=(action,label,disabled=false,css='')=>
    `<button type="button" class="${css}" data-la-action="${action}" ${disabled?'disabled':''}>${label}</button>`;
  const dialog=()=>shell.ensure('location-asset-edit-dialog','Manage Location Asset',()=>{
    state.slug='';state.pendingModel='';state.scan=null;state.scanStale=false;state.identityDraft=null;state.alphaDraft=null;state.atlas=window.game1ConsumerAtlasEditor.newState();
  });
  const close=()=>{const d=document.getElementById('location-asset-edit-dialog');if(d?.open)d.close();};
  function open(slug,initialTab='identity'){
    const item=decoAssetRow(slug);
    if(!item)return toast('Location Asset no longer exists; refresh.',true);
    if(state.busy)return toast('Finish the current operation first.',true);
    const d=dialog();if(d.open && state.slug!==slug)d.close();
    state.slug=slug;state.tab=initialTab;state.busy=false;state.scan=null;state.scanStale=false;state.pendingModel='';state.manualSlug=false;state.identityDraft=null;
    state.alphaDraft=null;state.inspection=item.fbxAnalysis||null;
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
    // Re-render preserves modal and scan list scrolling across async actions.
    const scrollBody=d.querySelector('.real-estate-mesh-dialog-body')?.scrollTop??0;
    const scrollList=d.querySelector('.la-sync-list')?.scrollTop??0;
    const historyOpen=Boolean(d.querySelector('.la-sync-controls details')?.open);
    const busy=state.busy||state.atlas.busy||decoAssetState.atlasBusy||Boolean(decoAssetState.syncingSlug);
    const configured=Boolean(decoAssetState.data?.publication?.configured);
    const modelCurrent=Boolean(item.model_asset_id&&item.model_sha256===item.model_published_sha256);
    const changed=Boolean(state.pendingModel||state.physicsDirty);
    const needsPublication=Boolean(state.pendingModel||!modelCurrent);
    const publicationReady=Boolean(configured&&(state.pendingModel||item.model_path));
    const tabs=[{id:'identity',label:'Identity'},{id:'model',label:'Model · FBX'},
      {id:'atlas',label:'Texture · atlas'}];
    const card=(name,description,content,status='',css='ready')=>shell.step(name,description,content,status,css);
    const identityData=state.identityDraft||{nameEn:item.name_en,slug:item.slug,
      category:item.category,surfaceMaterial:item.surfaceMaterial||'default',destructible:Boolean(item.destructible)};
    const identity=card('Registration details','Metadata changes never publish assets or modify Studio.',
      `<div class="deco-manage-fields"><label>Name<input data-la-name maxlength="120" value="${e(identityData.nameEn)}"></label>`+
      `<label>Slug<input data-la-slug maxlength="64" pattern="[a-z0-9_]+" value="${e(identityData.slug)}"></label>`+
      `<small class="muted">Изменение slug сохраняет опубликованные ID и историю. После переименования Place Registry покажет старые экземпляры для Repair.</small>`+
      `<label>Category<select data-la-category>${(decoAssetState.data?.options?.categories||[]).map(c=>
        `<option value="${e(c.id)}" ${c.id===identityData.category?'selected':''}>${e(c.label)}</option>`).join('')}</select></label>`+
      `<label>Surface material<select data-la-material>${(decoAssetState.data?.options?.surfaceMaterials||[]).map(m=>`<option value="${e(m.id)}" ${m.id===identityData.surfaceMaterial?'selected':''}>${e(m.label)}</option>`).join('')}</select><small class="muted">Physical surface and future impact/footstep sound family; COL receives the same.</small></label>`+
      `<label class="deco-policy-toggle"><input type="checkbox" data-la-destructible ${identityData.destructible?'checked':''}> Destructible</label></div>`+
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
    const activeAlpha=Boolean(item.alphaEnabled);
    const selectedAlpha=state.alphaDraft===null?activeAlpha:state.alphaDraft;
    const alphaDirty=selectedAlpha!==activeAlpha;
    const alphaEditor=`<section class="la-alpha-settings"><label class="deco-policy-toggle">`+
      `<input type="checkbox" data-la-alpha ${selectedAlpha?'checked':''} ${busy?'disabled':''}> Alpha transparency</label>`+
      `<small>${selectedAlpha?'Вкл. · Transparency':'Выкл. · Opaque'} · независимо от альфа-канала общего атласа; COL не изменяется.</small>`+
      `<div class="actions">${button('apply-alpha','Apply Changes',busy||!alphaDirty,alphaDirty?'asset-apply-ready':'')}</div></section>`;
    const atlas=alphaEditor+window.game1ConsumerAtlasEditor.render(state.atlas,{
      currentId:item.atlasVariantId||0,linked:item.atlasVariants||[],
      catalog:decoAssetState.data?.atlases||[],busy});
    const preview=state.scan;
    const scanValid=preview&&preview.modelId===String(item.model_asset_id||'')&&
      preview.atlasId===String(item.texture_asset_id||'')&&
      preview.revision===Number(item.bindingRevision||0)&&
      preview.alphaEnabled===Boolean(item.alphaEnabled);
    const selected=scanValid?preview.studio:null;
    const reportStale=Boolean(state.scanStale);
    // One card per placed Model; COLLIDER geometry is only a compact existence hint.
    // Selection and Sync operate on different contracts: Select is Explorer-only.
    const parts=selected?.parts||[];
    const grouped=[];
    const byModel=new Map();
    for(const part of parts){
      const identity=part.managed&&part.instanceId
        ?`managed:${part.instanceId}`:`model:${part.modelPath||part.path}`;
      let model=byModel.get(identity);
      if(!model){
        model={identity,parts:[],managed:part.managed,modelName:part.modelName||part.name,
          modelPath:part.modelPath||part.path};
        grouped.push(model);byModel.set(identity,model);
      }
      model.parts.push(part);
    }
    const pendingKeys=model=>model.parts.filter(p=>p.managed&&(p.needsMesh||p.needsTexture||p.needsAlpha)).map(p=>p.key);
    const inventory=selected?.inventory||[];
    const currentVersion=inventory.find(v=>v.modelAssetId===String(item.model_asset_id||''));
    const oldVersions=inventory.filter(v=>v!==currentVersion);
    const visualIds=(currentVersion?.meshes||[]).filter(m=>m.visualNames?.length).map(m=>m.meshId);
    const historyLine=(v,title)=>`<div><small><strong>${e(title)} · Model ID ${e(v.modelAssetId)}</strong></small>`+
      `<small>Mesh ID частей: ${(v.meshes||[]).map(m=>e(m.meshId)+(Number(m.count||0)>1?` ×${Number(m.count)}`:'')).join(', ')||'—'}</small></div>`;
    const inventoryDisplay=`<small>Model ID — версия публикации Roblox; Mesh ID — части внутри неё, `+
      `включая COL для поиска старых моделей.</small>`+
      (currentVersion?historyLine(currentVersion,'Сейчас'):'')+
      oldVersions.map((v,i)=>historyLine(v,`Ранее ${i+1}`)).join('');
    const meshLine=p=>{
      const meshStatus=p.meshCurrent?'✓ актуальный':'✕ устаревший';
      const textureStatus=p.textureCurrent?'✓ актуальный':'✕ устаревший';
      return `<div class="la-sync-visual"><strong>${e(p.name)}</strong>`+
        `<div class="la-sync-part-status"><span class="${p.meshCurrent?'is-current':'is-stale'}">Mesh ${meshStatus}</span>`+
        (p.textureApplicable?`<span class="${p.textureCurrent?'is-current':'is-stale'}">Texture ${textureStatus}</span>`:'')+`</div>`+
        `<small class="la-sync-ids">Mesh ID ${e(p.meshId||'—')}`+
        (p.textureApplicable?` · Texture ${e(p.textureId||'—')}`+
          (p.hasSurface?` · ColorMap ${e(p.colorMapId||'—')}`:'')+
          ` · Alpha ${p.alphaCurrent?'✓':'✕'} ${p.alphaEnabled?'Transparency':'Opaque'}`:'')+`</small></div>`;
    };
    const modelLine=(model,i)=>{
      const visuals=model.parts.filter(p=>!p.isCollider);
      const colliders=model.parts.filter(p=>p.isCollider);
      const pending=pendingKeys(model).length>0;
      const legacy=model.parts.find(p=>!p.managed&&p.attachable);
      const label=visuals[0]?.name||model.modelName;
      return `<div class="la-sync-model ${pending?'is-pending':''} ${model.managed?'':'is-external'}" `+
        `data-la-model-key="${e(model.parts[0].key)}" data-la-link-key="${e(legacy?.key||'')}">`+
        `<div class="la-sync-part-title"><strong>${i+1}. ${e(label)}</strong>`+
        `<small title="${e(model.modelPath)}">${e(model.modelPath)}</small></div>`+
        visuals.map(meshLine).join('')+
        `<small class="la-sync-col ${colliders.length?'':'is-missing'}">`+
        (colliders.length?`COL ✓ · ${colliders.length}`:'⚠ COL-меш не найден')+`</small>`+
        (!model.managed?'<small class="la-sync-external-note">Найдено по Mesh ID, без привязки к текущему ассету. '+
          'Для исправления идентификаторов используйте Repair в Place Registry; Find не изменяет Place.</small>':'')+
        `<div class="la-sync-part-actions">`+
          `${button('select-studio','Select in Studio',busy,'la-select-studio')}`+
          (legacy?button('attach-historical','Link historical model',busy):'')+
          (model.managed?button('sync-one','Sync',!pending||busy||reportStale):'')+'</div></div>';
    };
    const footer=card('Studio · Mesh & Texture Sync',
      'Поиск проверяет размещённые модели. Select выделяет в Studio; Sync обновляет только привязанные модели.',
      `<div class="actions">${button('scan','Find Mesh IDs · Studio',busy||item.status!=='PUBLISHED')}</div>`+
      (selected?`<div class="la-sync-current"><div><small>Актуальный Model ID</small><strong>${e(item.model_asset_id||'—')}</strong></div>`+
        `<div><small>Актуальные Mesh ID (визуальные)</small>`+
        `<strong>${visualIds.map(e).join(' · ')||'—'}</strong></div>`+
        `<div><small>Актуальный Texture ID · Atlas</small><strong>${e(item.texture_asset_id||'—')}</strong></div></div>`+
        `<div class="la-sync-counts"><strong>Найдено ${Number(selected.foundMeshParts||0)} MeshPart · `+
        `${grouped.length} моделей</strong>`+
        (reportStale?'<small class="la-sync-warning">Отчёт сохранён для просмотра. Требуется новый Find перед Sync.</small>':'')+
        `<small>Привязано: ${Number(selected.managedModels||0)} · `+
        `Исторических без привязки: ${grouped.filter(g=>!g.managed).length}</small>`+
        `<small>Геометрию обновить: ${Number(selected.geometryPending||0)} моделей · `+
        `Текстуру обновить: ${Number(selected.texturePending||0)} MeshPart · `+
        `Alpha обновить: ${Number(selected.alphaPending||0)} MeshPart</small></div>`+
        `<div class="la-sync-list">${grouped.map(modelLine).join('')||'<small>MeshPart не найдены.</small>'}</div>`:'')+
        `<div class="la-sync-controls"><div class="actions">`+
        `${button('select-all','Select All · Studio',busy||!grouped.length||reportStale)}`+
        `${button('replace-all','Sync All',busy||reportStale||item.status!=='PUBLISHED', selected&&parts.some(p=>p.managed&&(p.needsMesh||p.needsTexture||p.needsAlpha))?'asset-apply-ready':'')}</div>`+
        `<small>Sync обновляет только устаревшие ресурсы. При замене Mesh обновляется весь rig модели. `+
        `COL не получает текстуры. Перед изменением Place потребуется подтверждение.</small>`+
        (selected?`<details><summary>История Model / Mesh ID</summary>${inventoryDisplay}</details>`:'')+
        `</div>`,
      selected?'Проверка завершена':'Сначала Find',selected?'ready':'pending');
    d.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">Location Asset · ${e(item.slug)}</small>`+
      `<h3>Manage ${e(item.name_en)}</h3></div><button type="button" data-la-close aria-label="Close">✕</button></div>`+
      `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">${shell.tabs(tabs,state.tab,'data-la-tab')}`+
      `${state.tab==='identity'?identity:state.tab==='model'?model:atlas}${footer}`+
      `<div class="real-estate-workflow-result ${state.error?'issue':''}" role="status" ${state.result?'':'hidden'}>${e(state.result)}</div></div>`;
    d.querySelector('.real-estate-mesh-dialog-body').scrollTop=scrollBody;
    const newList=d.querySelector('.la-sync-list');if(newList)newList.scrollTop=scrollList;
    const history=d.querySelector('.la-sync-controls details');if(history)history.open=historyOpen;
    if(state.tab==='model')window.game1MeshAuthoring.wire(d,state.meshOptions,()=>{
      state.physicsDirty=true;
      const apply=d.querySelector('[data-la-action="apply-model"]');
      if(apply){apply.disabled=false;apply.classList.add('asset-apply-ready');}
    },Boolean(inspection?.hasCollider));
    d.querySelector('[data-la-close]').onclick=()=>{if(!busy)d.close();};
    d.querySelectorAll('[data-la-tab]').forEach(b=>b.onclick=()=>{if(!busy){state.tab=b.dataset.laTab;render();}});
    d.querySelectorAll('[data-la-action]').forEach(b=>b.onclick=()=>execute(b.dataset.laAction));
    const nameInput=d.querySelector('[data-la-name]');
    const slugInput=d.querySelector('[data-la-slug]');
    if(nameInput&&slugInput){
      window.game1LocationCategoryPicker?.mount(d.querySelector('[data-la-category]'),decoAssetState.data?.options);
      const updateDraft=()=>{state.identityDraft={nameEn:nameInput.value,
        slug:slugInput.value,category:d.querySelector('[data-la-category]').value,
        surfaceMaterial:d.querySelector('[data-la-material]').value,
        destructible:d.querySelector('[data-la-destructible]').checked};};
      slugInput.oninput=()=>{state.manualSlug=true;updateDraft();};
      nameInput.oninput=()=>{
        if(!state.manualSlug)slugInput.value=decoAssetSlugify(nameInput.value);
        updateDraft();
      };
      d.querySelector('[data-la-category]').onchange=updateDraft;
      d.querySelector('[data-la-material]').onchange=updateDraft;
      d.querySelector('[data-la-destructible]').onchange=updateDraft;
    }
    d.querySelectorAll('[data-la-action="select-studio"]').forEach(b=>{
      b.onclick=()=>selectInStudio([b.closest('[data-la-model-key]').dataset.laModelKey]);
    });
    d.querySelectorAll('[data-la-action="attach-historical"]').forEach(b=>{
      b.onclick=()=>attachHistorical(b.closest('[data-la-link-key]').dataset.laLinkKey);
    });
    d.querySelectorAll('[data-la-action="sync-one"]').forEach(b=>{
      b.onclick=()=>{
        const key=b.closest('[data-la-model-key]')?.dataset.laModelKey;
        const part=(state.scan?.studio?.parts||[]).find(p=>p.key===key);
        if(!part)return;
        const keys=(state.scan.studio.parts||[]).filter(p=>p.managed&&
          p.instanceId===part.instanceId&&(p.needsMesh||p.needsTexture||p.needsAlpha)).map(p=>p.key);
        return syncSelected(keys);
      };
    });
    const alphaInput=d.querySelector('[data-la-alpha]');
    if(alphaInput)alphaInput.onchange=()=>{state.alphaDraft=alphaInput.checked;render();};
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
    if(action==='apply-alpha')return run('Сохранение Alpha',async()=>{
      const current=row();if(!current)throw Error('Location Asset не найден');
      const value=state.alphaDraft===null?Boolean(current.alphaEnabled):state.alphaDraft;
      if(value===Boolean(current.alphaEnabled))return;
      const saved=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/appearance`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({alphaEnabled:value,expectedRevision:Number(current.revision)}),
      });
      await decoAssetLoad();
      state.alphaDraft=null;state.scanStale=true;
      message(`Alpha ${saved.alphaEnabled?'включён':'выключен'}. Model/Atlas ID не изменены. Нужен Sync размещённых моделей.`);
    });
    if(action==='delete')return decoAssetDelete(state.slug);
    if(action==='save-identity'){
      // Capture the user's edits BEFORE run() re-renders the modal as busy.
      const d=dialog();
      const nextSlug=d.querySelector('[data-la-slug]').value.trim().toLowerCase();
      const data={nameEn:d.querySelector('[data-la-name]').value.trim(),
        category:d.querySelector('[data-la-category]').value,
        surfaceMaterial:d.querySelector('[data-la-material]').value,
        destructible:d.querySelector('[data-la-destructible]').checked};
      return run('Applying metadata',async()=>{
      if(!/^[a-z0-9][a-z0-9_]{0,63}$/.test(nextSlug))throw Error('Slug: только a-z, 0-9 и _, не больше 64 символов');
      if(!data.nameEn)throw Error('Название не может быть пустым');
      if(nextSlug!==state.slug){
        if(!window.confirm(`Изменить slug ${state.slug} → ${nextSlug}?\n`+
          `Model/Mesh/Atlas ID не меняются. Исторические экземпляры сохраняются; `+
          `Place Registry потребует Repair для обновления имён и атрибутов.`)){
          message('Переименование отменено.');return;
        }
        const changed=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/rename-identity`,{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({...data,slug:nextSlug,expectedRevision:Number(item.revision)}),
        });
        state.slug=changed.slug;state.manualSlug=false;state.identityDraft=null;state.scan=null;
        await decoAssetLoad();await decoAssetShowSyncHistory(state.slug);
        message(`Slug обновлён: ${changed.previousSlug} → ${changed.slug}. `+
          'Place Registry распознаёт старые Mesh ID. Выполни Scan, затем Repair имён размещений.');
      }else{
        await decoAssetSaveEdits(state.slug,data,item.revision);
        state.manualSlug=false;state.identityDraft=null;
        message('Метаданные обновлены. Публикация и Studio не изменены.');
      }
      });
    }
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
    if(action==='scan')return run('Finding published Mesh IDs in Studio',async()=>{
      const result=await window.game1StudioSync.scanLocation(state.slug);
      state.scan={studio:result.studio,modelId:String(item.model_asset_id||''),
        atlasId:String(item.texture_asset_id||''),revision:Number(item.bindingRevision||0),
        alphaEnabled:Boolean(item.alphaEnabled)};
      state.scanStale=false;
      await decoAssetLoad(); // Registered Assets now shows scanned visual Mesh IDs.
      message(`Найдено MeshPart: ${result.studio.foundMeshParts}. `+
        `Без привязки: ${result.studio.unmanagedMeshParts}. Place не изменён.`);
    });
    if(action==='select-all'){
      const models=new Map();
      for(const part of state.scan?.studio?.parts||[]){
        const identity=part.managed&&part.instanceId
          ?`managed:${part.instanceId}`:`model:${part.modelPath||part.path}`;
        if(!models.has(identity))models.set(identity,part.key);
      }
      return selectInStudio([...models.values()]);
    }
    if(action==='replace-all')return syncAll();
  }
  async function selectInStudio(partKeys){
    return run('Выделение моделей в Studio',async()=>{
      const item=row(),scan=state.scan;
      if(!item||!scan||state.scanStale||scan.modelId!==String(item.model_asset_id||'')||
        scan.atlasId!==String(item.texture_asset_id||'')||
        scan.revision!==Number(item.bindingRevision||0)||
        scan.alphaEnabled!==Boolean(item.alphaEnabled))throw Error('Проверка устарела. Нажми Find.');
      if(!Array.isArray(partKeys)||!partKeys.length||
        partKeys.some(key=>!(scan.studio.parts||[]).some(part=>part.key===key)))
        throw Error('Нечего выделять в Studio');
      const selected=await window.game1StudioSync.selectLocation(state.slug,scan.studio.scanToken,partKeys);
      message(`В Studio выделено моделей: ${selected.studio.selectedCount}. Place не изменён.`);
    });
  }
  async function syncAll(){
    const item=row();if(!item||state.busy)return;
    const valid=state.scan&&state.scan.modelId===String(item.model_asset_id||'')&&
      state.scan.atlasId===String(item.texture_asset_id||'')&&
      state.scan.revision===Number(item.bindingRevision||0)&&
      state.scan.alphaEnabled===Boolean(item.alphaEnabled);
    if(!valid||state.scanStale){
      state.scanStale=true;
      await execute('scan');
      if(!state.scan||state.scanStale)return;
    }
    const keys=(state.scan.studio.parts||[]).filter(p=>p.managed&&
      (p.needsMesh||p.needsTexture||p.needsAlpha)).map(p=>p.key);
    if(!keys.length){
      message(state.scan.studio.unmanagedMeshParts?
        'Среди привязанных моделей изменений нет. Исторические модели не изменены.':
        'Все размещённые модели актуальны. Изменений не требуется.');
      return render();
    }
    return syncSelected(keys);
  }
  async function attachHistorical(partKey){
    return run('Linking verified historical Model',async()=>{
      const item=row(),scan=state.scan;
      if(!item||!scan||state.scanStale||scan.modelId!==String(item.model_asset_id||'')||
        scan.atlasId!==String(item.texture_asset_id||'')||
        scan.revision!==Number(item.bindingRevision||0)||
        scan.alphaEnabled!==Boolean(item.alphaEnabled))throw Error('Scan is stale; Find again');
      const part=(scan.studio.parts||[]).find(p=>p.key===partKey&&!p.managed&&p.attachable);
      if(!part)throw Error('Историческую модель нельзя безопасно привязать');
      if(typeof window.confirm!=='function')throw Error('Explicit confirmation unavailable');
      if(!window.confirm(`Привязать модель ${part.path} к ${state.slug}? `+
        `Старая публикация ${part.historicalModelId}. Изменятся только метки, не геометрия. Продолжить?`)){
        message('Привязка отменена. Place не изменён.');return;
      }
      const token=scan.studio.scanToken;
      state.scanStale=true;
      await window.game1StudioSync.attachLocation(state.slug,token,partKey);
      const updated=await window.game1StudioSync.scanLocation(state.slug);
      state.scan={studio:updated.studio,modelId:String(item.model_asset_id||''),
        atlasId:String(item.texture_asset_id||''),revision:Number(item.bindingRevision||0),
        alphaEnabled:Boolean(item.alphaEnabled)};
      state.scanStale=false;
      message(`Модель привязана к ${state.slug}. Геометрия не изменена. Проверь статусы и нажми Sync.`);
    });
  }
  async function refreshSyncReport(){
    const current=row();
    if(!current)throw Error('Location Asset больше не зарегистрирован');
    const refreshed=await window.game1StudioSync.scanLocation(state.slug);
    state.scan={studio:refreshed.studio,modelId:String(current.model_asset_id||''),
      atlasId:String(current.texture_asset_id||''),revision:Number(current.bindingRevision||0),
      alphaEnabled:Boolean(current.alphaEnabled)};
    state.scanStale=false;
  }
  async function syncSelected(keys){
    return run('Синхронизация моделей',async()=>{
      const item=row(),scan=state.scan;
      if(!item||!scan||state.scanStale||scan.modelId!==String(item.model_asset_id||'')||
        scan.atlasId!==String(item.texture_asset_id||'')||
        scan.revision!==Number(item.bindingRevision||0)||
        scan.alphaEnabled!==Boolean(item.alphaEnabled)){
        throw Error('Отчёт Find устарел; повтори сканирование');
      }
      const pending=new Map((scan.studio.parts||[]).filter(p=>p.managed&&
        (p.needsMesh||p.needsTexture||p.needsAlpha)).map(p=>[p.key,p]));
      if(!Array.isArray(keys)||!keys.length||new Set(keys).size!==keys.length||
        keys.some(key=>!pending.has(key)))throw Error('Нет доступных для Sync MeshPart');
      const chosen=keys.map(key=>pending.get(key));
      const mesh=chosen.some(p=>p.needsMesh),texture=chosen.some(p=>p.needsTexture),alpha=chosen.some(p=>p.needsAlpha);
      const label=mesh&&texture?'Replace Texture + Mesh':mesh?'Replace Mesh':texture?'Replace Texture':alpha?'Sync Alpha':'Sync';
      if(typeof window.confirm!=='function')throw Error('Explicit confirmation is unavailable');
      const scope=mesh?'Mesh: заменится весь rig соответствующей модели. ':texture?'Texture: обновятся выбранные визуальные MeshPart. ':'Alpha: изменится только SurfaceAppearance.AlphaMode. ';
      if(!window.confirm(`${label}: ${keys.length} MeshPart (${state.slug}). `+
        scope+'Сделай резервную копию Place. Продолжить?')){
        message('Sync отменён. Place не изменён.');return;
      }
      // The token is single use, but keep the displayed snapshot while Studio
      // works. If Sync fails, the last report is still readable (stale/locked).
      state.scanStale=true;
      let result;
      try{
        result=await window.game1StudioSync.replaceLocation(state.slug,scan.studio.scanToken,keys);
      }catch(error){
        try{await refreshSyncReport();}
        catch(_refreshError){state.scanStale=true;}
        throw error;
      }
      const summary=window.game1StudioSync.locationSummary(state.slug,result.studio)+
        (result.studio.fullySynced?' Синхронизация завершена.':' Частичное обновление.');
      try{
        await decoAssetLoad();
        await decoAssetShowSyncHistory(state.slug);
        await refreshSyncReport();
        message(summary+' Список обновлён.');
      }catch(error){
        state.scanStale=true;
        message(summary+' Повторный Find не удался: '+(error?.message||String(error))+
          '. Старый отчёт сохранён; нажми Find.',true);
      }
    });
  }
  function startScan(slug){
    open(slug,'model');
    return execute('scan');
  }
  return Object.freeze({open,close,render,startScan});
})();
