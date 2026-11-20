/* M234 · Location Assets editor. Published Model and shared Atlas remain independent.
 * Atlas presentation/selection is the SAME consumer editor as Real Estate.
 */
window.game1LocationAssetWorkflow = (() => {
  const state={slug:'',tab:'model',busy:false,result:'',error:false,manualSlug:false,identityDraft:null,modelAppearanceDraft:null,
    pendingModel:'',pendingLod1:'',inspection:null,meshOptions:{},physicsDirty:false,scan:null,scanStale:false,alphaDraft:null,publication:null,
    atlas:window.game1ConsumerAtlasEditor.newState()};
  const shell=window.game1AssetWorkflowDialog;
  const e=value=>esc(String(value??''));
  const row=()=>decoAssetRow(state.slug);
  // A binding revision/Atlas ID alone cannot identify an Appearance revision:
  // switching Atlas -> Material + Color can preserve both Model and Mesh IDs.
  const appearanceSignature=item=>JSON.stringify([
    item?.appearanceMode||'atlas', item?.visualMaterial||'SmoothPlastic',
    item?.visualColor||'#FFFFFF', item?.meshOptions||{},
  ]);
  const hasUnsavedIdentity=()=>{
    const current=row(),draft=state.identityDraft;
    return Boolean(current&&draft&&(
      draft.appearanceMode!==current.appearanceMode||
      draft.visualMaterial!==current.visualMaterial||
      draft.visualColor!==current.visualColor));
  };
  const button=(action,label,disabled=false,css='')=>
    `<button type="button" class="${css}" data-la-action="${action}" ${disabled?'disabled':''}>${label}</button>`;
  const dialog=()=>shell.ensure('location-asset-edit-dialog','Manage Location Asset',()=>{
    state.slug='';state.pendingModel='';state.pendingLod1='';state.scan=null;state.scanStale=false;state.identityDraft=null;state.modelAppearanceDraft=null;state.alphaDraft=null;state.publication=null;state.atlas=window.game1ConsumerAtlasEditor.newState();
  });
  const close=()=>{const d=document.getElementById('location-asset-edit-dialog');if(d?.open)d.close();};
  function open(slug,initialTab='identity'){
    const item=decoAssetRow(slug);
    if(!item)return toast('Location Asset no longer exists; refresh.',true);
    if(state.busy)return toast('Finish the current operation first.',true);
    const d=dialog();if(d.open && state.slug!==slug)d.close();
    state.slug=slug;state.tab=initialTab;state.busy=false;state.scan=null;state.scanStale=false;state.pendingModel='';state.pendingLod1='';state.manualSlug=false;state.identityDraft=null;state.modelAppearanceDraft=null;
    state.alphaDraft=null;state.publication=null;state.inspection=item.fbxAnalysis||null;
    state.meshOptions=window.game1MeshAuthoring.seeded(state.inspection,item.meshOptions||{});
    state.physicsDirty=false;state.atlas=window.game1ConsumerAtlasEditor.newState();
    message('');render();if(!d.open)d.showModal();
    decoAssetShowSyncHistory(slug);
  }
  function message(text,isError=false){state.result=String(text||'');state.error=Boolean(isError);}
  function rememberStudioVerification(item,studio){
    if(!item||!studio)return;
    decoAssetState.studioVerifications ||= {};
    decoAssetState.studioVerifications[item.slug]={
      modelId:String(item.model_asset_id||''),atlasId:String(item.texture_asset_id||''),
      bindingRevision:Number(item.bindingRevision||0),authoringRevision:Number(item.revision||0),
      alphaEnabled:Boolean(item.alphaEnabled),appearanceMode:item.appearanceMode||'atlas',
      visualMaterial:item.visualMaterial||'SmoothPlastic',visualColor:item.visualColor||'#FFFFFF',
      surfaceMaterial:item.surfaceMaterial||'default',
      verification:studio.verification||'review_required',
    };
  }
  async function run(label,task){
    if(state.busy)return;
    state.busy=true;state.operationLabel=label;message(`${label}…`);render();
    try{return await task();}
    catch(error){message(error?.message||String(error),true);return null;}
    finally{state.busy=false;state.operationLabel='';render();}
  }
  async function prepareAuthoredRigIfMissing(setStage){
    const current=row();
    if(!current)throw Error('Location Asset no longer exists');
    const analysis=current.fbxAnalysis||state.inspection;
    if(!analysis)throw Error('Analyze registered FBX before publication');
    if(!window.game1LocationPublication.needsCanonicalFbx({model_path:current.model_path,fbxAnalysis:analysis}))return false;
    setStage?.('Подготавливаем канонический rig_carrier в Blender (новая FBX-ревизия)…');
    const prepared=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/prepare-canonical-fbx`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({expectedRevision:Number(current.revision)}),
    });
    if(prepared.resourceKind!=='ModelSource'||prepared.atlasUnchanged!==true||!prepared.structuralHash)
      throw Error('Blender authoring did not confirm canonical FBX and unchanged Atlas');
    await decoAssetLoad();
    state.inspection=row()?.fbxAnalysis||null;
    state.meshOptions=window.game1MeshAuthoring.seeded(state.inspection,row()?.meshOptions||{});
    state.physicsDirty=false;
    state.scanStale=true;
    return true;
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
    const publication=window.game1LocationPublication.plan(item,
      decoAssetState.data?.atlases||[],Boolean(state.pendingModel));
    const needsPublication=publication.modelNeeded;
    const publicationReady=Boolean(configured&&(state.pendingModel||item.model_path));
    const showPublish=publication.count>0||state.tab==='publish'||Boolean(state.publication);
    const tabs=[{id:'identity',label:'Identity'},{id:'model',label:'Model · FBX'},
      {id:'lod1',label:'LOD1'},
      {id:'atlas',label:'Texture · atlas'},
      ...(showPublish?[{id:'publish',label:`Publish${publication.count?' · '+publication.count:''}`}]:[])];
    const card=(name,description,content,status='',css='ready')=>shell.step(name,description,content,status,css);
    const identityData=state.identityDraft||{nameEn:item.name_en,slug:item.slug,
      category:item.category,surfaceMaterial:item.surfaceMaterial||'default',destructible:Boolean(item.destructible),
      appearanceMode:item.appearanceMode||'atlas',visualMaterial:item.visualMaterial||'SmoothPlastic',
      visualColor:item.visualColor||'#FFFFFF'};
    const identity=card('Registration details','Metadata changes never publish assets or modify Studio.',
      `<div class="deco-manage-fields"><label>Name<input data-la-name maxlength="120" value="${e(identityData.nameEn)}"></label>`+
      `<label>Slug<input data-la-slug maxlength="64" pattern="[a-z0-9_]+" value="${e(identityData.slug)}"></label>`+
      `<small class="muted">Изменение slug сохраняет опубликованные ID и историю. После переименования Place Registry покажет старые экземпляры для Repair.</small>`+
      `<label>Category<select data-la-category>${(decoAssetState.data?.options?.categories||[]).map(c=>
        `<option value="${e(c.id)}" ${c.id===identityData.category?'selected':''}>${e(c.label)}</option>`).join('')}</select></label>`+
      `<label>Object material · interaction sounds<select data-la-material>${(decoAssetState.data?.options?.surfaceMaterials||[]).map(m=>`<option value="${e(m.id)}" ${m.id===identityData.surfaceMaterial?'selected':''}>${e(m.label)}</option>`).join('')}</select><small class="muted">Sound family only; never changes the visible material.</small></label>`+
      `<label class="deco-policy-toggle"><input type="checkbox" data-la-destructible ${identityData.destructible?'checked':''}> Destructible</label></div>`+
      `<div class="actions">${button('save-identity','Apply Changes',busy)}${button('delete','Retire asset',busy)}</div>`,
      `Revision ${Number(item.revision||0)}`);
    const inspection=state.inspection;
    const needsAuthoredRig=window.game1LocationPublication.needsCanonicalFbx({
      model_path:state.pendingModel||item.model_path, fbxAnalysis:inspection});
    // Shared default is edited alongside per-MeshPart overrides, never in Identity.
    // Every visual MeshPart inherits this default unless explicitly overridden.
    const modelAppearance=state.modelAppearanceDraft||{
      appearanceMode:item.appearanceMode||'atlas',
      visualMaterial:item.visualMaterial||'SmoothPlastic',
      visualColor:item.visualColor||'#FFFFFF'};
    const modelAppearanceEditor=`<section class="la-model-appearance">`+
      `<strong>Default MeshPart appearance</strong>`+
      `<small>Used only by MeshParts without an individual override below.</small>`+
      `<label>Appearance source<select data-la-model-appearance-mode>`+
      `<option value="atlas" ${modelAppearance.appearanceMode==='atlas'?'selected':''}>Texture Atlas</option>`+
      `<option value="material" ${modelAppearance.appearanceMode==='material'?'selected':''}>Roblox Material + Color</option>`+
      `<option value="material_atlas" ${modelAppearance.appearanceMode==='material_atlas'?'selected':''}>Roblox Material + Color + Atlas</option>`+
      `</select></label>`+
      `<div data-la-model-visual-fields ${modelAppearance.appearanceMode==='atlas'?'hidden':''}>`+
      `<label>Visual material<select data-la-model-visual-material>${(decoAssetState.data?.options?.visualMaterials||[]).map(m=>
        `<option value="${e(m.id)}" ${m.id===modelAppearance.visualMaterial?'selected':''} ${m.requiresTexture&&modelAppearance.appearanceMode==='material'?'disabled':''}>${e(m.label)}${m.requiresTexture?' · requires texture':''}</option>`).join('')}</select></label>`+
      `<label>Color<input type="color" data-la-model-visual-color value="${e(modelAppearance.visualColor)}"></label>`+
      `</div></section>`;
    const model=card('Model · FBX',
      'Review mesh names, skeleton and collision settings. A changed FBX is published as a NEW Model ID; physics-only changes do not publish.',
      `<small class="deco-manage-value">${e(state.pendingModel||item.model_path||'No FBX selected')}</small>`+
      modelAppearanceEditor+
      window.game1MeshAuthoring.inspectionView(inspection,state.meshOptions,'location-mesh',{
        materials:decoAssetState.data?.options?.visualMaterials||[],
        atlases:decoAssetState.data?.atlases||[],alphaEnabled:Boolean(item.alphaEnabled)})+
      (Object.entries(item.meshOptions||{}).filter(([name,settings])=>
        settings?.appearanceMode&&settings.atlasVariantId&&!settings.texture_asset_id)
        .map(([name,settings])=>`<div class="la-publication-resource"><span>${e(name)} · Atlas not published</span>`+
          button(`publish-mesh-atlas:${settings.atlasVariantId}`,'Publish atlas',busy)+`</div>`).join(''))+
      (item.collisionBlueprintNeedsCapture?'<small class="la-publication-warning">Collision Blueprint is incompatible with the current published Mesh ID. Existing collision history is preserved, but NEW placements will have no generated collision until you Capture a new blueprint.</small>':'')+
      (needsAuthoredRig?'<small class="la-publication-warning">В FBX есть кости, но нет rig_carrier. Перед публикацией Blender подготовит каноническую FBX-версию. Исходник будет сохранён, Atlas ID не изменится.</small>':'')+
      `<div class="actions">${button('choose-fbx','Choose FBX',busy)}${button('inspect-fbx','Analyze saved FBX',busy||!item.model_path)}</div>`+
      `<div class="shared-model-state"><small>Roblox Model ID: <strong>${e(item.model_asset_id||'Not published')}</strong></small>`+
      `<small>${needsAuthoredRig?'Canonical rig_carrier authoring required before new Model ID.':modelCurrent?'Current FBX revision is published.': 'Publication required for current FBX revision.'}</small></div>`+
      `<div class="actions">${button('apply-model',needsPublication?'Publish and Apply':'Apply Changes',
        busy||(!changed&&!needsPublication)||(needsPublication&&!publicationReady),
        changed||needsPublication?'asset-apply-ready':'')}</div>`,
      modelCurrent?'Published':'Changes pending',modelCurrent?'ready':'pending');
    const activeAlpha=Boolean(item.alphaEnabled);
    const selectedAlpha=state.alphaDraft===null?activeAlpha:state.alphaDraft;
    const alphaDirty=selectedAlpha!==activeAlpha;
    const alphaEditor=`<section class="la-alpha-settings"><label class="deco-policy-toggle">`+
      `<input type="checkbox" data-la-alpha ${selectedAlpha?'checked':''} ${busy?'disabled':''}> Alpha transparency</label>`+
      `<small>${selectedAlpha?'Вкл. · Transparency':'Выкл. · Opaque'} · независимо от альфа-канала общего атласа; Физические Parts настраиваются отдельно.</small>`+
      `<div class="actions">${button('apply-alpha','Apply Changes',busy||!alphaDirty,alphaDirty?'asset-apply-ready':'')}</div></section>`;
    const atlas=(item.appearanceMode==='material'
      ? '<small class="hint">Material + Color active: no Image ID is required. To switch to Atlas, choose a registered variant below. This changes the appearance mode but does not modify Studio until Sync.</small>'+
        `<label>Existing atlas variant<select data-la-switch-atlas>`+
        `<option value="">Choose a variant…</option>`+
        (decoAssetState.data?.atlases||[]).flatMap(f=>f.variants||[]).filter(v=>!v.retired)
          .map(v=>`<option value="${Number(v.id)}">${e(v.filename)}${v.published_id?' · published':' · publish required'}</option>`).join('')+
        `</select></label><div class="actions">${button('activate-atlas','Use selected atlas',busy)}</div>`
      : alphaEditor+window.game1ConsumerAtlasEditor.render(state.atlas,{
      currentId:item.atlasVariantId||0,linked:item.atlasVariants||[],
      catalog:decoAssetState.data?.atlases||[],busy,openPublish:publication.atlasNeeded,
      offerPublication:true}));
    // Publication is a separate operation from source registration and Studio Sync.
    // Busy stages show the actual awaited network operation, not a fabricated %.
    const publicationStatus=(key,label,pending)=>{
      const progress=state.publication?.[key]||'';
      const text=progress==='running'?'Publishing…':progress==='done'?'Published ✓':
        progress==='error'?'Publication failed':pending?'Ready for publication':'Published ✓';
      return `<div class="la-publication-resource"><div><strong>${label}</strong><small>${text}</small></div>`+
        `<span class="${progress==='running'?'la-publish-spinner':''}" aria-hidden="true"></span></div>`;
    };
    const publishPanel=card('Publish resources',
      'Регистрация сохраняет исходники. Публикация создаёт Roblox ID. Studio Sync выполняется отдельно.',
      `<div class="la-publication-stack">`+
      (item.appearanceMode==='material'?'':publicationStatus('atlas',`Atlas · ${e(publication.variant?.filename||'не выбран')}`,publication.atlasNeeded))+
      publicationStatus('model','Model · FBX',publication.modelNeeded)+`</div>`+
      (state.physicsDirty&&!publication.modelNeeded?'<p class="la-publication-warning">Есть изменения физических настроек MeshPart. Сохрани их через Model · FBX → Apply Changes.</p>':'')+
      (publication.reviewRequired?'<p class="la-publication-warning">Атлас уже имеет Image ID, но изменён. Для замены общего атласа открой Texture · atlas и подтверди замену после просмотра.</p>':'')+
      `<div class="la-publication-stage" role="status" aria-live="polite">`+
      (state.publication?.active?`<span class="${state.publication.running?'la-publish-spinner':''}" aria-hidden="true"></span><span>${e(state.publication.active)}</span>`:
        publication.count?'Готово к публикации · Place не будет изменён.':'Все выбранные ресурсы опубликованы.')+
      `</div><div class="actions">${button('publish-ready',`Publish ready · ${publication.count}`,
        busy||!publication.count||!configured,'la-publish-primary '+(publication.count?'asset-apply-ready':''))}</div>`+
      (!configured&&publication.count?'<small class="la-publication-warning">Настрой Open Cloud, чтобы опубликовать ресурсы.</small>':'')+
      `<small>Публикация атласа не перепубликует Model. Публикация Model не публикует атлас. `+
      `Если один этап завершится ошибкой, успешный ID сохранится, повторятся только незавершённые этапы.</small>`,
      publication.count?`${publication.count} ожидает публикации`:'Готово',publication.count?'pending':'ready');
    const lod=item.lod1||{revision:0,status:'NOT_REGISTERED',modelAssetId:'',sourcePath:''};
    const lodStatus={NOT_REGISTERED:'Не зарегистрирован',STAGED:'FBX сохранён · ожидает публикации',
      UPDATE_AVAILABLE:'Новая ревизия · ожидает публикации',PUBLISHED:'Опубликован',
      SOURCE_MISSING:'Исходный FBX не найден'}[lod.status]||lod.status;
    const lodPanel=card('LOD1 · облегчённая Model',
      'Необязательный ресурс. Не меняет FULL, Atlas, Collision или размещённые объекты.',
      `<div class="deco-manage-fields"><small>Статус: <strong>${e(lodStatus)}</strong> · ревизия ${Number(lod.revision||0)}</small>`+
      `<small>LOD1 Model ID: <strong>${e(lod.modelAssetId||'—')}</strong></small>`+
      `<small>Имя FBX и Roblox Model: <strong>${e(state.slug+'_lod1')}</strong> · файл ${e(state.slug+'_lod1.fbx')}</small>`+
      `<small>FBX: ${e(lod.sourcePath||'—')}</small>`+
      (state.pendingLod1?`<small>Выбрано: ${e(state.pendingLod1)}</small>`:'')+
      `<div class="actions">${button('choose-lod1','Choose LOD1 FBX',busy)}`+
      `${button('stage-lod1','Register LOD1',busy||!state.pendingLod1,'asset-apply-ready')}`+
      `${button('publish-lod1','Publish LOD1',busy||!configured||!['STAGED','UPDATE_AVAILABLE'].includes(lod.status),'la-publish-primary')}</div>`+
      `<small>Каждая публикация создаёт новый Model ID. Размещение и LOD-переключение в Studio пока не включены.</small></div>`,
      lodStatus,lod.status==='PUBLISHED'?'ready':'pending');
    const errorStatus=state.error&&state.result?`<div class="real-estate-workflow-result issue la-operation-error" role="alert">${e(state.result)}</div>`:'';
    const busyStatus=busy&&state.tab!=='publish'?`<div class="la-operation-status" role="status" aria-live="polite"><span class="la-publish-spinner" aria-hidden="true"></span>${e(state.operationLabel||state.result||'Подготовка ресурса…')}</div>`:'';
    const preview=state.scan;
    const scanValid=preview&&preview.modelId===String(item.model_asset_id||'')&&
      preview.atlasId===String(item.texture_asset_id||'')&&
      preview.revision===Number(item.bindingRevision||0)&&
      preview.alphaEnabled===Boolean(item.alphaEnabled)&&
      preview.appearanceSignature===appearanceSignature(item);
    const selected=scanValid?preview.studio:null;
    const reportStale=Boolean(state.scanStale);
    // One card per placed Model; dedicated COL meshes are retired.
    // Selection and Sync operate on different contracts: Select is Explorer-only.
    const parts=selected?.parts||[];
    const grouped=window.game1LocationSyncGrouping.models(parts);
    // LandscapePainter owns placement, not geometry publication. Find lists
    // its published Mesh IDs; the authoritative Painter integrity check runs
    // inside Place Registry before any appearance mutation.
    const painterModel=model=>!model.managed&&model.parts.some(p=>p.painterCandidate===true);
    const painterModels=grouped.filter(painterModel);
    const hasManagedPending=parts.some(p=>p.managed&&!p.republishRequired&&!p.needsFbxInspection&&
      (p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics));
    const pendingKeys=model=>model.parts.filter(p=>p.managed&&!p.republishRequired&&!p.needsFbxInspection&&
      (p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics)).map(p=>p.key);
    const inventory=selected?.inventory||[];
    const currentVersion=inventory.find(v=>v.modelAssetId===String(item.model_asset_id||''));
    const oldVersions=inventory.filter(v=>v!==currentVersion);
    const visualIds=(currentVersion?.meshes||[]).filter(m=>m.visualNames?.length).map(m=>m.meshId);
    const historyLine=(v,title)=>`<div><small><strong>${e(title)} · Model ID ${e(v.modelAssetId)}</strong></small>`+
      `<small>Mesh ID частей: ${(v.meshes||[]).map(m=>e(m.meshId)+(Number(m.count||0)>1?` ×${Number(m.count)}`:'')).join(', ')||'—'}</small></div>`;
    const inventoryDisplay=`<small>Model ID — версия публикации Roblox; Mesh ID — части внутри неё, `+
      `включая части исторических публикаций.</small>`+
      (currentVersion?historyLine(currentVersion,'Сейчас'):'')+
      oldVersions.map((v,i)=>historyLine(v,`Ранее ${i+1}`)).join('');
    const meshLine=p=>{
      const meshStatus=p.meshCurrent?'✓ актуальный':'✕ устаревший';
      const textureStatus=p.textureCurrent?'✓ актуальный':'✕ устаревший';
      const appearanceLabel=item.appearanceMode==='material'?'Appearance':'Texture';
      const physics=p.physics;
      const physicsText=physics?`C/Q/T ${physics.canCollide?'1':'0'}/${physics.canQuery?'1':'0'}/${physics.canTouch?'1':'0'} → `+
        `${physics.expectedCanCollide?'1':'0'}/${physics.expectedCanQuery?'1':'0'}/${physics.expectedCanTouch?'1':'0'} · `+
        `DoubleSided ${physics.doubleSided?'1':'0'} → ${physics.expectedDoubleSided?'1':'0'} · `+
        `Fidelity ${e(physics.collisionFidelity)} → ${e(physics.expectedCollisionFidelity)}`:'';
      return `<div class="la-sync-visual"><strong>${e(p.name)}</strong>`+
        (p.effectiveAppearanceMode?`<small>Studio expects: ${e(p.effectiveAppearanceMode)}${p.appearanceOverride?' · MeshPart override':''}</small>`:'')+
        `<div class="la-sync-part-status"><span class="${p.meshCurrent?'is-current':'is-stale'}">Mesh ${meshStatus}</span>`+
        (p.textureApplicable?`<span class="${p.textureCurrent?'is-current':'is-stale'}">Texture ${textureStatus}</span>`:'')+
        (p.textureApplicable?`<span class="${p.physicsCurrent?'is-current':'is-stale'}">Physics ${p.physicsCurrent?'✓ актуальна':'✕ требует Sync'}</span>`:'')+`</div>`+
        (p.needsPhysics?`<small class="la-sync-external-note">${physicsText}</small>`:'')+
        `<small class="la-sync-ids">Mesh ID ${e(p.meshId||'—')}`+
        (p.textureApplicable?(item.appearanceMode==='material'?` · Material ${e(item.visualMaterial)} · Color ${e(item.visualColor)}`:
          ` · Texture ${e(p.textureId||'—')}`+(item.appearanceMode==='material_atlas'?` · Material ${e(item.visualMaterial)} · Color ${e(item.visualColor)}`:''))+
          (p.hasSurface?` · ColorMap ${e(p.colorMapId||'—')}`:'')+
          (item.appearanceMode==='material'?'':` · Alpha ${p.alphaCurrent?'✓':'✕'} ${p.alphaEnabled?'Transparency':'Opaque'}`):'')+`</small></div>`;
    };
    const modelLine=(model,i)=>{
      const visuals=model.parts.filter(p=>!p.isCollider);
      const pending=pendingKeys(model).length>0;
      const republish=model.parts.some(p=>p.republishRequired);
      const needsNewPlacement=model.parts.some(p=>p.needsCanonicalReplacement);
      const needsInspection=model.parts.some(p=>p.needsFbxInspection);
      const legacy=model.parts.find(p=>!p.managed&&p.attachable);
      const label=visuals[0]?.name||model.modelName;
      return `<div class="la-sync-model ${pending?'is-pending':''} ${model.managed?'':'is-external'}" `+
        `data-la-model-key="${e(model.parts[0].key)}" data-la-link-key="${e(legacy?.key||'')}">`+
        `<div class="la-sync-part-title"><strong>${i+1}. ${e(label)}</strong>`+
        `<small title="${e(model.modelPath)}">${e(model.modelPath)}</small></div>`+
        visuals.map(meshLine).join('')+
        (republish?'<small class="la-sync-external-note">Импортный RootPart или некорректная структура — требуется исправить исходный FBX и перепубликовать Model. rig_carrier нужен только при наличии Bone. Атлас остаётся прежним. Repair не изменит скелет.</small>':'')+
        (needsNewPlacement?'<small class="la-sync-external-note">Новый Model ID имеет каноническую структуру. Явный Sync загрузит эту опубликованную Model и целиком заменит подтверждённый старый дочерний rig. Корневая Model, parent, pivot, CFrame и масштаб размещения сохраняются; Repair не используется.</small>':'')+
        (needsInspection?'<small class="la-sync-external-note">Неизвестно, есть ли кости в опубликованном FBX. Сначала Analyze saved FBX; перепубликация пока не требуется.</small>':'')+
        (!model.managed?(painterModel(model)?
          '<small class="la-sync-external-note">Подвес LandscapePainter · сохраняет авторское крепление и эффекты. '+
          'Sync All проверит атлас, полный риг, stem, tether, sway и затем обновит только внешний вид. '+
          'Неисправные подвесы не изменяются.</small>':
          '<small class="la-sync-external-note">Найдено по Mesh ID, без подтверждённого владельца. '+
          'Find не изменяет Place; произвольные объекты не синхронизируются.</small>'):'')+
        `<div class="la-sync-part-actions">`+
          `${button('select-studio','Select in Studio',busy,'la-select-studio')}`+
          (legacy?button('attach-historical','Link historical model',busy):'')+
          (needsInspection?button('inspect-fbx','Analyze saved FBX',busy):'')+
          (model.managed?button('sync-one','Sync',!pending||busy||reportStale):'')+'</div></div>';
    };
    const footer=card('Studio · Mesh & Appearance Sync',
      'Поиск проверяет размещённые модели. Select выделяет в Studio; Sync обновляет только привязанные модели.',
      `<div class="actions">${button('scan','Find Mesh IDs · Studio',busy)}</div>`+
      (selected?`<div class="la-sync-current"><div><small>Актуальный Model ID</small><strong>${e(item.model_asset_id||'—')}</strong></div>`+
        `<div><small>Актуальные Mesh ID (визуальные)</small>`+
        `<strong>${visualIds.map(e).join(' · ')||'—'}</strong></div>`+
        `<div><small>${item.appearanceMode==='material'?'Визуальный материал / цвет':'Актуальный Texture ID · Atlas'}</small><strong>${item.appearanceMode==='material'?e(item.visualMaterial+' · '+item.visualColor):e(item.texture_asset_id||'—')+(item.appearanceMode==='material_atlas'?` · ${e(item.visualMaterial+' · '+item.visualColor)}`:'')}</strong></div></div>`+
        `<div class="la-sync-counts"><strong>Найдено ${Number(selected.foundMeshParts||0)} MeshPart · `+
        `${grouped.length} моделей</strong>`+
        (reportStale?'<small class="la-sync-warning">Отчёт сохранён для просмотра. Требуется новый Find перед Sync.</small>':'')+
        `<small>Привязано: ${Number(selected.managedModels||0)} · `+
        `DecoManager: ${Number(selected.managedModels||0)} · LandscapePainter: ${painterModels.length} · `+
        `Другие без привязки: ${grouped.filter(g=>!g.managed&&!painterModel(g)).length}</small>`+
        `<small>Геометрию обновить: ${Number(selected.geometryPending||0)} моделей · `+
        `${item.appearanceMode==='material'?'Внешний вид обновить':'Текстуру обновить'}: ${Number(selected.texturePending||0)} MeshPart · `+
        `Alpha обновить: ${Number(selected.alphaPending||0)} MeshPart · `+
        `Physics обновить: ${Number(selected.physicsPending||0)} MeshPart</small></div>`+
        `<div class="la-sync-list">${grouped.map(modelLine).join('')||'<small>MeshPart не найдены.</small>'}</div>`:'')+
        `<div class="la-sync-controls"><div class="actions">`+
        `${button('select-all','Select All · Studio',busy||!grouped.length||reportStale)}`+
        `${button('replace-all','Sync All',busy||reportStale||(!hasManagedPending&&!painterModels.length),hasManagedPending||painterModels.length?'asset-apply-ready':'')}</div>`+
        `<small>Обычный Sync All проверяет и DecoManager, и LandscapePainter. `+
        `Подвесы проходят структурную проверку; обновляется только внешний вид, `+
        `без перестройки rig_carrier, света, огня, костей и креплений.</small>`+
        (selected?`<details><summary>История Model / Mesh ID</summary>${inventoryDisplay}</details>`:'')+
        `</div>`,
      selected?'Проверка завершена':'Сначала Find',selected?'ready':'pending');
    d.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small class="eyebrow">Location Asset · ${e(item.slug)}</small>`+
      `<h3>Manage ${e(item.name_en)}</h3></div><button type="button" data-la-close aria-label="Close">✕</button></div>`+
      `<div class="real-estate-mesh-dialog-body" aria-busy="${busy}">${shell.tabs(tabs,state.tab,'data-la-tab')}${errorStatus}${busyStatus}`+
      `${state.tab==='identity'?identity:state.tab==='model'?model:state.tab==='lod1'?lodPanel:state.tab==='atlas'?atlas:publishPanel}${['publish','lod1'].includes(state.tab)?'':footer}`+
      `${state.error?'':`<div class="real-estate-workflow-result" role="status" ${state.result?'':'hidden'}>${e(state.result)}</div>`}</div>`;
    d.querySelector('.real-estate-mesh-dialog-body').scrollTop=state.error?0:scrollBody;
    const newList=d.querySelector('.la-sync-list');if(newList)newList.scrollTop=scrollList;
    const history=d.querySelector('.la-sync-controls details');if(history)history.open=historyOpen;
    if(state.tab==='model'){
      const readModelAppearance=()=>{
        state.modelAppearanceDraft={
          appearanceMode:d.querySelector('[data-la-model-appearance-mode]').value,
          visualMaterial:d.querySelector('[data-la-model-visual-material]').value,
          visualColor:d.querySelector('[data-la-model-visual-color]').value};
        state.physicsDirty=true;
        const apply=d.querySelector('[data-la-action="apply-model"]');
        if(apply){apply.disabled=false;apply.classList.add('asset-apply-ready');}
      };
      for(const selector of ['[data-la-model-appearance-mode]',
          '[data-la-model-visual-material]','[data-la-model-visual-color]']){
        const field=d.querySelector(selector);
        if(field)field.onchange=()=>{
          readModelAppearance();
          if(selector==='[data-la-model-appearance-mode]')render();
        };
      }
      window.game1MeshAuthoring.wire(d,state.meshOptions,()=>{
      state.physicsDirty=true;
      const apply=d.querySelector('[data-la-action="apply-model"]');
      if(apply){apply.disabled=false;apply.classList.add('asset-apply-ready');}
    },Boolean(inspection?.hasCollider),{
      materials:decoAssetState.data?.options?.visualMaterials||[],
      atlases:decoAssetState.data?.atlases||[],alphaEnabled:Boolean(item.alphaEnabled)});
    }
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
          p.instanceId===part.instanceId&&!p.republishRequired&&!p.needsFbxInspection&&
          (p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics)).map(p=>p.key);
        return syncSelected(keys);
      };
    });
    const alphaInput=d.querySelector('[data-la-alpha]');
    if(alphaInput)alphaInput.onchange=()=>{state.alphaDraft=alphaInput.checked;render();};
    if(state.tab==='atlas'&&item.appearanceMode!=='material')window.game1ConsumerAtlasEditor.wire(d,state.atlas,{
      consumerType:'location_asset',slug:state.slug,
      revision:item.bindingRevision||0,busy:state.busy,
      getRevision:()=>row()?.bindingRevision||0,getCurrentId:()=>row()?.atlasVariantId||0,
      catalog:decoAssetState.data?.atlases||[],
      filePicker:'/api/files/choose-location-asset-texture',
      onOpenPublish:()=>{state.tab='publish';render();},
      onPublishAtlas:variantId=>run('Публикация выбранного атласа',async()=>{
        const result=await publishInitialAtlas(variantId);
        const warnings=(result.exportWarnings||[]).join(' | ');
        message(`Atlas опубликован · Image ID ${result.publishedAssetId}. `+
          'Активная привязка и Studio не изменены.'+(warnings?` Предупреждение: ${warnings}`:''),Boolean(warnings));
        return true;
      }),
      onMessage:message,onRender:render,onRefresh:decoAssetLoad,
    });
  }
  // Shared first-publication operation: used both by Publish ready and by an
  // unpublished atlas dot. Neither operation selects an atlas or Syncs Studio.
  async function publishInitialAtlas(variantId){
    const current=row();
    if(!current)throw Error('Location Asset больше не найден');
    const result=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/publish-pending-atlas`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({variantId:Number(variantId),
        expectedRevision:Number(current.bindingRevision||0)}),
    });
    if(result.resourceKind!=='Atlas'||!result.publishedAssetId)
      throw Error('Atlas publication did not confirm a new Image ID; inspect history before retrying');
    await decoAssetLoad();
    state.scanStale=true;
    return result;
  }
  async function execute(action){
    const item=row();if(!item)return;
    if(action==='activate-atlas')return run('Подключение атласа',async()=>{
      const chosen=Number(dialog()?.querySelector('[data-la-switch-atlas]')?.value||0);
      if(!Number.isInteger(chosen)||chosen<1)throw Error('Выбери вариант атласа');
      await request(`/api/location-assets/${encodeURIComponent(state.slug)}/atlas-binding`,{
        method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({variantId:chosen,expectedRevision:Number(item.revision)}),
      });
      await decoAssetLoad();state.scanStale=true;state.identityDraft=null;
      message('Режим Atlas включён. При необходимости опубликуй Image ID и выполни Studio Sync.');
    });
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
    if(action==='publish-ready')return run('Publishing new resources',async()=>{
      const initial=window.game1LocationPublication.plan(row(),decoAssetState.data?.atlases||[],Boolean(state.pendingModel));
      if(!initial.count){message('Все выбранные ресурсы уже опубликованы.');return;}
      state.tab='publish';
      state.publication={atlas:initial.atlasNeeded?'waiting':'',
        model:initial.modelNeeded?'waiting':'',active:'',running:false};
      const stage=(key,label,status)=>{
        state.publication[key]=status;
        state.publication.active=label;
        state.publication.running=status==='running';
        render();
      };
      let completed=0;
      try{
        // Publish atlas first: the registration has already staged its source
        // in the independent Atlas Registry; do not make the user choose it again.
        if(initial.atlasNeeded){
          stage('atlas','Публикуем выбранный Atlas в Roblox Open Cloud…','running');
          const result=await publishInitialAtlas(initial.variant.id);
          stage('atlas',`Atlas опубликован · Image ID ${result.publishedAssetId}`,'done');
          completed++;
          if(result.exportWarnings?.length)message(result.exportWarnings.join(' | '),true);
        }
        if(initial.modelNeeded){
          if(state.pendingModel||state.physicsDirty){
            stage('model','Сохраняем выбранный FBX и настройки мешей…','running');
            await decoAssetSaveEdits(state.slug,{
              ...(state.pendingModel?{modelSourcePath:state.pendingModel}:{}),
              meshOptions:state.meshOptions},Number(row().revision));
            state.pendingModel='';state.physicsDirty=false;
            state.inspection=row()?.fbxAnalysis||state.inspection;
          }
          await prepareAuthoredRigIfMissing(label=>stage('model',label,'running'));
          stage('model','Публикуем Model в Roblox Open Cloud…','running');
          const result=await decoAssetPublish(state.slug,'model',false);
          stage('model',`Model опубликован · Model ID ${result.model_asset_id}`,'done');
          completed++;
          state.scanStale=true;
        }
        state.publication.active=`Готово: опубликовано ${completed} ресурс(а). Studio Sync отдельно.`;
        state.publication.running=false;
        if(!state.error)message(state.publication.active);
      }catch(error){
        // A remote upload can complete even when the response is lost. Refresh
        // published IDs before a user retries; never assume a failed HTTP
        // response means Roblox did not create an asset.
        try{await decoAssetLoad();}catch(refreshError){
          // Preserve the original publication failure if ID refresh also fails.
        }
        const key=state.publication.model==='running'?'model':'atlas';
        state.publication[key]='error';
        state.publication.active=`Ошибка этапа ${key==='atlas'?'Atlas':'Model'}: ${error?.message||String(error)}. `+
          `Уже подтверждено: ${completed}. Проверь обновлённые ID перед повторным запуском.`;
        state.publication.running=false;
        throw Error(state.publication.active);
      }
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
        state.manualSlug=false;state.identityDraft=null;state.scanStale=true;
        message('Метаданные обновлены. Для Studio Sync нужен новый Find — Appearance изменён.');
      }
      });
    }
    if(action.startsWith('publish-mesh-atlas:'))return run('Publishing MeshPart Atlas',async()=>{
      const variantId=Number(action.split(':')[1]);
      if(!Number.isSafeInteger(variantId)||variantId<1)throw Error('Invalid Atlas variant');
      const result=await request(`/api/texture-atlases/variants/${variantId}/publish`,{method:'POST'});
      await decoAssetLoad();
      message(`Atlas published · Image ID ${result.published_id||'see Atlas Registry'}. Sync Studio after saving changes.`);
    });
    if(action==='choose-lod1')return run('Выбор LOD1 FBX',async()=>{
      const chosen=await request('/api/files/choose-location-asset-model',{method:'POST'});
      if(!chosen?.path){message('Выбор LOD1 отменён.');return;}
      state.pendingLod1=chosen.path;
      message('LOD1 FBX выбран. Нажми Register LOD1; FULL и Studio не изменятся.');
    });
    if(action==='stage-lod1')return run('Регистрация LOD1',async()=>{
      if(!state.pendingLod1)throw Error('Выбери FBX для LOD1');
      const saved=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/lod1-stage`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({sourcePath:state.pendingLod1,
          expectedRevision:Number(row()?.lod1?.revision||0)}),
      });
      state.pendingLod1='';await decoAssetLoad();
      message(`LOD1 FBX зарегистрирован · ревизия ${saved.revision}. Публикация отдельно.`);
    });
    if(action==='publish-lod1')return run('Публикация LOD1',async()=>{
      const before=row();
      if(!before||!['STAGED','UPDATE_AVAILABLE'].includes(before.lod1?.status))
        throw Error('Нет новой ревизии LOD1 для публикации');
      try{
        const result=await request(`/api/location-assets/${encodeURIComponent(state.slug)}/lod1-publish`,{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({expectedRevision:Number(before.lod1.revision)}),
        });
        await decoAssetLoad();
        message(`LOD1 опубликован · Roblox Model ID ${result.modelAssetId}. FULL / Studio не изменены.`);
      }catch(error){
        try{await decoAssetLoad();}catch(_ignored){}
        throw Error((error?.message||String(error))+' Проверь LOD1 Model ID перед повторной публикацией.');
      }
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
      state.physicsDirty=false;state.scanStale=true;
      message('FBX analysis updated without publication. Run Find again to confirm the placement.');
    });
    if(action==='apply-model')return run('Applying Model changes',async()=>{
      const needsSave=Boolean(state.pendingModel||state.physicsDirty);
      if(needsSave){
        await decoAssetSaveEdits(state.slug,{
          ...(state.pendingModel?{modelSourcePath:state.pendingModel}:{}),
          meshOptions:state.meshOptions,
          ...(state.modelAppearanceDraft||{})},item.revision);
        state.modelAppearanceDraft=null;
        state.pendingModel='';state.physicsDirty=false;state.scanStale=true;
        state.inspection=row()?.fbxAnalysis||state.inspection;
      }
      const current=row();
      if(!current.model_asset_id||current.model_sha256!==current.model_published_sha256||
          window.game1LocationPublication.needsCanonicalFbx(current)){
        await prepareAuthoredRigIfMissing(label=>{state.operationLabel=label;render();});
        const result=await decoAssetPublish(state.slug,'model',false);
        message(`Model published · new ID ${result.model_asset_id}. Atlas ID ${result.texture_asset_id||'—'} unchanged. Use Studio Sync below to update placed instances.`);
      }else message('Mesh settings applied. Published Model ID unchanged. Use Studio Sync below to apply physics in Place.');
    });
    if(action==='scan')return run('Finding published Mesh IDs in Studio',async()=>{
      const result=await window.game1StudioSync.scanLocation(state.slug);
      state.scan={studio:result.studio,modelId:String(item.model_asset_id||''),
        atlasId:String(item.texture_asset_id||''),revision:Number(item.bindingRevision||0),
        alphaEnabled:Boolean(item.alphaEnabled),
        appearanceSignature:appearanceSignature(item)};
      state.scanStale=false;
      rememberStudioVerification(item,result.studio);
      await decoAssetLoad(); // Registered Assets now shows scanned visual Mesh IDs.
      const confirmation=result.studio.verification==='current'
        ? ' Изменений нет; опубликованные ID подтверждены без Replace.'
        : result.studio.verification==='pending'
          ? ' Есть реальные изменения — проверь список перед Sync.'
          : ' Нужна проверка непривязанных или некорректных моделей.';
      message(`Найдено MeshPart: ${result.studio.foundMeshParts}. `+
        `Без привязки: ${result.studio.unmanagedMeshParts}. Place не изменён.`+confirmation);
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
        (scan.alphaEnabled!==Boolean(item.alphaEnabled)||
        scan.appearanceSignature!==appearanceSignature(item)))throw Error('Проверка устарела. Нажми Find.');
      if(!Array.isArray(partKeys)||!partKeys.length||
        partKeys.some(key=>!(scan.studio.parts||[]).some(part=>part.key===key)))
        throw Error('Нечего выделять в Studio');
      const selected=await window.game1StudioSync.selectLocation(state.slug,scan.studio.scanToken,partKeys);
      message(`В Studio выделено моделей: ${selected.studio.selectedCount}. Place не изменён.`);
    });
  }
  async function syncPainter(models){
    return run('Проверка и обновление подвесов LandscapePainter',async()=>{
      const item=row(),current=state.scan;
      if(!item||!current||state.scanStale||current.modelId!==String(item.model_asset_id||'')||
        current.atlasId!==String(item.texture_asset_id||'')||
        current.revision!==Number(item.bindingRevision||0)||
        (current.alphaEnabled!==Boolean(item.alphaEnabled)||
        current.appearanceSignature!==appearanceSignature(item)))throw Error('Данные изменились; снова выполни Find');
      // Same Place Registry service, authoritative Studio Scan and guarded
      // shared Sync. It preserves the Painter rig/tether, while applying
      // published appearance, visual physics and registered collision Parts.
      const scanned=(await request('/api/location-place-registry',{method:'POST',
        body:JSON.stringify({phase:'scan'})})).studio;
      if(scanned.incomplete)throw Error('Проверка опубликованных Mesh ID неполная; Studio не изменена');
      const protectedRows=(scanned.protected||[]).filter(p=>
        p.kind==='landscape_attachment'&&p.slug===state.slug);
      const reviews=protectedRows.filter(p=>p.review);
      const painterRows=protectedRows.filter(p=>p.canSync&&(p.needsTexture||p.needsOwnerCleanup||p.needsPhysics||p.needsCollision)&&p.key);
      // The Find report is a locator only. A mismatch must never silently
      // authorize a subset of a suspicious Painter assembly.
      if(protectedRows.length!==models.length || reviews.length){
        const details=reviews.slice(0,3).map(p=>`${p.name}: ${p.reason}`).join('; ');
        throw Error(`Проверка LandscapePainter: в Find ${models.length}, подтверждено ${protectedRows.length}; `+
          `структурных проблем ${reviews.length}. ${details||'Проверь метки владельца, риг и авторские подвесы.'}`);
      }
      if(!painterRows.length){
        const stale=(models||[]).some(m=>m.parts.some(p=>p.needsTexture||p.needsAlpha));
        if(stale)throw Error('Find и структурный Scan расходятся по Appearance. Изменений нет; повтори Find и проверь эффективный режим каждого MeshPart.');
        message(`Подвесы ${state.slug} актуальны по проверке Studio. Изменений не требуется.`);return;
      }
      if(typeof window.confirm!=='function')throw Error('Подтверждение сохранения Place недоступно');
      if(!window.confirm(`Sync Appearance · ${state.slug}: ${painterRows.length} подвесов.\n`+
        `Сохрани резервную копию Place. Проверены опубликованные Mesh ID, риг, крепление, `+
        `трос и sway. Применятся внешний вид, MeshPart collision policy и `+
        `Collision Blueprint. Fire, Light, Bone, Attachment, stem и line сохраняются. Продолжить?`)){
        message('Sync отменён. Place не изменён.');return;
      }
      state.scanStale=true;
      const changed=(await request('/api/location-place-registry',{method:'POST',body:JSON.stringify({
        phase:'sync',scanToken:scanned.scanToken,keys:painterRows.map(p=>p.key),
      })})).studio;
      if(changed.changed!==painterRows.length||changed.skipped?.length)
        throw Error(`Studio подтвердила ${changed.changed} из ${painterRows.length}; `+
          `проверь Place и выполни Find: ${(changed.skipped||[]).join('; ')}`);
      // Read the *actual* Studio MeshPart state after the transaction. A bridge
      // success flag is not proof that TextureID/SurfaceAppearance were removed.
      const audit=(await request('/api/location-place-registry',{method:'POST',
        body:JSON.stringify({phase:'scan'})})).studio;
      const touched=new Set(painterRows.map(p=>p.path));
      const checked=(audit.protected||[]).filter(p=>p.kind==='landscape_attachment'&&
        p.slug===state.slug&&touched.has(p.path));
      const bad=checked.filter(p=>p.review||p.needsTexture||p.needsOwnerCleanup||p.needsPhysics||p.needsCollision);
      if(checked.length!==touched.size||bad.length){
        state.scanStale=true;
        throw Error(`Sync запущен, но проверка Properties не подтверждена: ${checked.length}/${touched.size} подвесов; `+
          `${bad.map(p=>p.name+': '+p.reason).join('; ')||'неполный список'}. `+
          'Проверь Studio, повтори Find; не публикуй Place до устранения расхождения.');
      }
      await decoAssetLoad();
      await refreshSyncReport();
      if(typeof decoAssetRender==='function')decoAssetRender();
      message(`Обновлено ${changed.changed} подвесов ${state.slug}. `+
        `Структура, свет, огонь и крепления не менялись; выполнен повторный Find.`);
    });
  }

  async function syncAll(){
    const item=row();if(!item||state.busy)return;
    if(hasUnsavedIdentity()){
      message('Сначала нажми Apply Changes в Identity: выбранный Material/Color ещё не сохранён.',true);
      return render();
    }
    const valid=state.scan&&state.scan.modelId===String(item.model_asset_id||'')&&
      state.scan.atlasId===String(item.texture_asset_id||'')&&
      state.scan.revision===Number(item.bindingRevision||0)&&
      state.scan.alphaEnabled===Boolean(item.alphaEnabled)&&
      state.scan.appearanceSignature===appearanceSignature(item);
    if(!valid||state.scanStale){
      state.scanStale=true;
      await execute('scan');
      if(!state.scan||state.scanStale)return;
    }
    const keys=(state.scan.studio.parts||[]).filter(p=>p.managed&&
      !p.republishRequired&&!p.needsFbxInspection&&
      (p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics)).map(p=>p.key);
    const painterModels=window.game1LocationSyncGrouping.models(state.scan.studio.parts||[]).filter(m=>
      !m.managed&&m.parts.some(p=>p.painterCandidate===true));
    if(!keys.length&&!painterModels.length){
      message('Все подтверждённые размещения актуальны. Непривязанные объекты не изменены.');return render();
    }
    // They have different Studio ownership/Undo transactions. Keep their
    // mutations separate and report partial success rather than lying about
    // a single atomic operation when both owners coexist.
    if(keys.length)await syncSelected(keys);
    if(painterModels.length){
      if(keys.length){
        const result=await window.game1StudioSync.scanLocation(state.slug);
        state.scan={studio:result.studio,modelId:String(item.model_asset_id||''),
          atlasId:String(item.texture_asset_id||''),revision:Number(item.bindingRevision||0),
          alphaEnabled:Boolean(item.alphaEnabled),
        appearanceSignature:appearanceSignature(item)};
        state.scanStale=false;
      }
      return syncPainter(painterModels);
    }
  }
  async function attachHistorical(partKey){
    return run('Linking verified historical Model',async()=>{
      const item=row(),scan=state.scan;
      if(!item||!scan||state.scanStale||scan.modelId!==String(item.model_asset_id||'')||
        scan.atlasId!==String(item.texture_asset_id||'')||
        scan.revision!==Number(item.bindingRevision||0)||
        (scan.alphaEnabled!==Boolean(item.alphaEnabled)||
        scan.appearanceSignature!==appearanceSignature(item)))throw Error('Scan is stale; Find again');
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
        alphaEnabled:Boolean(item.alphaEnabled),
        appearanceSignature:appearanceSignature(item)};
      state.scanStale=false;
      rememberStudioVerification(row(),updated.studio);
      await decoAssetLoad();
      message(`Модель привязана к ${state.slug}. Геометрия не изменена. Проверь статусы и нажми Sync.`);
    });
  }
  async function refreshSyncReport(){
    const current=row();
    if(!current)throw Error('Location Asset больше не зарегистрирован');
    const refreshed=await window.game1StudioSync.scanLocation(state.slug);
    state.scan={studio:refreshed.studio,modelId:String(current.model_asset_id||''),
      atlasId:String(current.texture_asset_id||''),revision:Number(current.bindingRevision||0),
      alphaEnabled:Boolean(current.alphaEnabled),
        appearanceSignature:appearanceSignature(current)};
    state.scanStale=false;
    rememberStudioVerification(row(),refreshed.studio);
  }
  async function syncSelected(keys){
    return run('Синхронизация моделей',async()=>{
      const item=row(),scan=state.scan;
      if(!item||!scan||state.scanStale||scan.modelId!==String(item.model_asset_id||'')||
        scan.atlasId!==String(item.texture_asset_id||'')||
        scan.revision!==Number(item.bindingRevision||0)||
        (scan.alphaEnabled!==Boolean(item.alphaEnabled)||
        scan.appearanceSignature!==appearanceSignature(item))){
        throw Error('Отчёт Find устарел; повтори сканирование');
      }
      const pending=new Map((scan.studio.parts||[]).filter(p=>p.managed&&
        !p.republishRequired&&!p.needsFbxInspection&&
        (p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics)).map(p=>[p.key,p]));
      if(!Array.isArray(keys)||!keys.length||new Set(keys).size!==keys.length||
        keys.some(key=>!pending.has(key)))throw Error('Нет доступных для Sync MeshPart');
      const chosen=keys.map(key=>pending.get(key));
      const mesh=chosen.some(p=>p.needsMesh),texture=chosen.some(p=>p.needsTexture),alpha=chosen.some(p=>p.needsAlpha),physics=chosen.some(p=>p.needsPhysics);
      const label=mesh&&texture?'Replace Texture + Mesh':mesh?'Replace Mesh':texture?'Replace Texture':alpha?'Sync Alpha':physics?'Sync Physics':'Sync';
      if(typeof window.confirm!=='function')throw Error('Explicit confirmation is unavailable');
      const scope=mesh?'Mesh: заменится весь rig соответствующей модели. ':texture?'Texture: обновятся выбранные визуальные MeshPart. ':alpha?'Alpha: изменится только SurfaceAppearance.AlphaMode. ':'Physics: применятся зарегистрированные CanCollide / CanQuery / CanTouch / DoubleSided / CollisionFidelity. ';
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
        await decoAssetLoad(); // Refresh published identity before rescanning.
        await decoAssetShowSyncHistory(state.slug);
        await refreshSyncReport();
        if(typeof decoAssetRender==='function')decoAssetRender(); // Use the new Find verdict.
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
