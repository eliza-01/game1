/* MNPC authoring: one static mesh/atlas revision for either actor kind. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const base = '/api/lod-manager/mnpc';
  const key = item => `${item.kind}:${item.slug}`;
  const path = item => `${base}/${encodeURIComponent(item.kind)}/${encodeURIComponent(item.slug)}`;
  const post = (url, payload={}) => request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const state = {data:null, selected:'', busy:false, history:[], paths:{fbx:'',texture:'',pose:'',poseAtlas:''}};
  state.recipe={frame:1,targetTriangles:1000,textureSize:512,reviewedAssembly:false};
  const statuses = {NOT_REGISTERED:'Missing LOD1',FULL_UNAVAILABLE:'FULL unavailable',FULL_CHANGED:'Stale · FULL changed',IDLE_CHANGED:'Stale · idle changed',
    SOURCE_MISSING:'Missing source',SOURCE_CHANGED:'Changed source',ATLAS_CHANGED:'Stale · atlas changed',ATLAS_SOURCE_CHANGED:'Atlas source changed',STAGED:'Staged',
    ATLAS_READY:'Atlas ready',MODEL_PENDING:'Model operation pending',PUBLISHED:'Published'};
  const filter = $('mnpc-lod-filter');
  try {const saved=window.localStorage?.getItem('game1.lod.mnpc.filter');if(['all','monster','npc'].includes(saved))filter.value=saved;} catch (_) {}
  if(!filter.value)filter.value='all';
  const item = () => state.data?.items.find(row=>key(row)===state.selected);
  function profileFields(prefix,p) {
    return `<div class="lm-setting-grid lm-mnpc-profile">
      <label class="lm-checkbox">Enabled · Runtime<input id="${prefix}-enabled" type="checkbox" ${p.enabled?'checked':''}></label>
      <label>FULL · studs<input id="${prefix}-full" type="number" min="1" max="10000" step="1" value="${esc(p.full)}"></label>
      <label>Unload · studs<input id="${prefix}-hide" type="number" min="1" max="10000" step="1" value="${esc(p.hide)}"></label>
      <label>Hysteresis ±<input id="${prefix}-hysteresis" type="number" min="0" max="100" step="1" value="${esc(p.hysteresis)}"></label></div>`;
  }
  function readProfile(prefix) {
    const n=field=>{const raw=$(`${prefix}-${field}`).value;const value=Number(raw);if(!raw.trim()||!Number.isSafeInteger(value))throw Error('Введите целое число studs');return value;};
    return {enabled:$(`${prefix}-enabled`).checked,full:n('full'),hide:n('hide'),hysteresis:n('hysteresis')};
  }
  function message(text) {$('mnpc-lod-message').textContent=text;}
  function renderRows() {
    const data=state.data;
    const term=$('mnpc-lod-search').value.trim().toLowerCase();
    const rows=(data?.items||[]).filter(row=>(filter.value==='all'||row.kind===filter.value)&&
      (!term||`${row.name} ${row.slug}`.toLowerCase().includes(term)));
    $('mnpc-lod-count').textContent=data?`${rows.length} / ${data.items.length}`:'';
    $('mnpc-lod-rows').innerHTML=rows.length?rows.map(row=>{
      const color=row.status==='PUBLISHED'?'ready':row.status==='STAGED'||row.status==='ATLAS_READY'?'warning':'empty';
      return `<tr><td><b>${esc(row.name)}</b><small>${esc(row.kind)} · ${esc(row.slug)}</small></td>
        <td>${esc(row.fullStatus)}<small>${esc(row.fullModelId)} · r${esc(row.fullRevision)}</small></td>
        <td><span class="lm-chip lm-${color}">${esc(statuses[row.status]||row.status)}</span><small>${row.geometry?`${esc(row.geometry.triangles)} tri · `:''}r${esc(row.revision)} · ${row.runtimeReady?'Mesh':'Red dummy'}</small></td>
        <td>${esc(row.profile.full)} / ${esc(row.profile.hide)} ±${esc(row.profile.hysteresis)}<small>${row.inherits?'Default':'Override'} · ${row.profile.enabled?'On':'Off'}</small></td>
        <td><button type="button" data-mnpc-edit="${esc(key(row))}" ${state.busy?'disabled':''}>Edit</button></td></tr>`;
    }).join(''):'<tr><td colspan="5">Нет подходящих существ.</td></tr>';
  }
  function render() {
    renderRows();
    const data=state.data;
    $('mnpc-lod-defaults').innerHTML=data?`${profileFields('mnpc-default',data.settings.defaults)}
      <div class="actions"><button type="button" data-mnpc-action="save-default">Save defaults</button></div>`:'';
    const row=item(), editor=$('mnpc-lod-editor');
    editor.hidden=!row;
    if(!row){editor.innerHTML='';return;}
    const g=row.geometry, stageAllowed=Boolean(row.fullFingerprint)&&row.status!=='MODEL_PENDING';
    const publishAllowed=['STAGED','ATLAS_READY'].includes(row.status)||(row.status==='MODEL_PENDING'&&Boolean(row.modelOperation));
    const alignAllowed=row.status==='PUBLISHED'&&g?.preparation?.mode==='captured_idle'&&g.preparation.rootSpace==='roblox_navigation_studs_y_up';
    const history=state.history.length?state.history.map(h=>`<div class="lm-revision">r${esc(h.revision)} · ${esc(h.event)}<small>Model ${esc(h.modelAssetId||'—')} · Image ${esc(h.imageAssetId||'—')}</small>${h.operation?`<small>${esc(h.operation)}</small>`:''}</div>`).join(''):'<p class="lm-note">Нет истории.</p>';
    editor.innerHTML=`<div class="lm-list-head"><div><h4>${esc(row.name)} · ${esc(row.kind)}</h4><p class="lm-note">${esc(row.reason||statuses[row.status])}</p></div><button type="button" data-mnpc-action="close">Close</button></div>
      <div class="lm-meta">FULL fingerprint: ${esc(row.fullFingerprint||'—')}<br>Model ID: ${esc(row.modelAssetId||'—')} · Image ID: ${esc(row.imageAssetId||'—')}${row.atlasVariantId?` · Atlas #${esc(row.atlasVariantId)}`:''}${row.moderationState?` · ${esc(row.moderationState)}`:''}</div>
      ${g?`<p class="lm-note">${esc(g.vertices)} vertices · ${esc(g.triangles)} triangles · FBX scene bounds: ${esc(g.boundsMin.map(n=>n.toFixed(3)).join(', '))} → ${esc(g.boundsMax.map(n=>n.toFixed(3)).join(', '))}<br>${esc(row.sourcePath)}</p>`:''}
      <details><summary>FULL visual source / equipment</summary><pre class="lm-mnpc-source">${esc(JSON.stringify(row.fullIdentity,null,2))}</pre></details>
      <details open><summary>Capture FULL idle · Studio</summary>
        <p class="lm-note">Studio Edit + актуальные Rojo / Model + Atlas. Захват опубликованного idle, экипировки, вершин и UV в координатах навигационного root. Cloud не изменяется.</p>
        <div class="actions"><button type="button" data-mnpc-action="capture" ${stageAllowed?'':'disabled'}>Capture idle &amp; geometry</button></div>
        <p class="lm-note">${state.capture?.status==='CAPTURED'?`Captured · ${esc(state.capture.meshCount)} meshes · ${esc(state.capture.boneCount)} bones · idle ${esc(state.capture.animationId)} · ${esc(state.capture.pose.time.toFixed(3))} s`:esc(state.capture?.status||'NOT_CAPTURED')}${state.capture?.geometryReady?` · ${esc(state.capture.triangleCount)} triangles`:''}</p>
        <div class="lm-setting-grid lm-mnpc-profile">
          <label>Triangle cap<input id="mnpc-bake-targetTriangles" type="number" min="100" max="10000" step="1" value="${esc(state.recipe.targetTriangles)}"></label>
          <label>Atlas max side<select id="mnpc-bake-textureSize">${[128,256,512,1024].map(n=>`<option value="${n}" ${Number(state.recipe.textureSize)===n?'selected':''}>${n}</option>`).join('')}</select></label>
        </div>
        <div class="actions"><button type="button" data-mnpc-action="bake" ${stageAllowed&&state.capture?.geometryReady?'':'disabled'}>Bake &amp; stage LOD1</button></div>
        <p class="lm-note">Общий цветовой атлас, без PBR-карт; нативное соответствие позы/UV и масштаба проверяется в Studio перед Runtime.</p>
      </details>
      <details><summary>Prepare LOD1 · posed assembly</summary>
        <p class="lm-note">Пилот: готовая поза FULL (включая оружие) и общий UV-атлас. Сборка, упрощение и уменьшение текстуры выполняются автоматически; Ручной импорт — альтернативный путь для неподдерживаемых автоматическим захватом вариантов.</p>
        <div class="lm-mnpc-files"><label>Posed assembly FBX<input id="mnpc-prepare-pose" value="${esc(state.paths.pose)}" ${stageAllowed?'':'disabled'}></label>
          <button type="button" data-mnpc-action="choose-pose" ${stageAllowed?'':'disabled'}>Choose FBX</button>
          <label>Common UV atlas<input id="mnpc-prepare-poseAtlas" value="${esc(state.paths.poseAtlas)}" ${stageAllowed?'':'disabled'}></label>
          <button type="button" data-mnpc-action="choose-pose-atlas" ${stageAllowed?'':'disabled'}>Choose atlas</button></div>
        <div class="lm-setting-grid lm-mnpc-profile">
          <label>FBX frame<input id="mnpc-prepare-frame" type="number" min="-100000" max="100000" step="1" value="${esc(state.recipe.frame)}"></label>
          <label>Triangle cap<input id="mnpc-prepare-targetTriangles" type="number" min="100" max="10000" step="1" value="${esc(state.recipe.targetTriangles)}"></label>
          <label>Atlas max side<select id="mnpc-prepare-textureSize">${[128,256,512,1024].map(n=>`<option value="${n}" ${Number(state.recipe.textureSize)===n?'selected':''}>${n}</option>`).join('')}</select></label>
        </div>
        <label class="lm-checkbox"><input id="mnpc-prepare-reviewedAssembly" type="checkbox" ${state.recipe.reviewedAssembly?'checked':''}>Подтверждаю соответствие FULL, экипировки, позы и общего UV-атласа</label>
        <div class="actions"><button type="button" data-mnpc-action="prepare" ${stageAllowed?'':'disabled'}>Generate &amp; stage</button></div>
        ${g?.preparation?`<p class="lm-note">Prepared: ${esc(g.preparation.inputTriangles)} → ${esc(g.triangles)} tri · ${esc(g.preparation.inputMeshes)} input meshes · ${esc(g.preparation.outputTextureSize.join(' × '))} px · ${esc(g.preparation.mode)}</p>`:''}
      </details>
      <div class="lm-mnpc-files"><label>Prepared static FBX · ${esc(row.slug)}_lod1.fbx<input id="mnpc-stage-fbx" value="${esc(state.paths.fbx)}" placeholder="FBX path" ${stageAllowed?'':'disabled'}></label>
        <button type="button" data-mnpc-action="choose-fbx" ${stageAllowed?'':'disabled'}>Choose FBX</button>
        <label>Baked texture · PNG/JPEG<input id="mnpc-stage-texture" value="${esc(state.paths.texture)}" placeholder="Texture path" ${stageAllowed?'':'disabled'}></label>
        <button type="button" data-mnpc-action="choose-texture" ${stageAllowed?'':'disabled'}>Choose texture</button></div>
      <div class="actions"><button type="button" data-mnpc-action="stage" ${stageAllowed?'':'disabled'}>Stage LOD1</button>
        <button type="button" class="primary" data-mnpc-action="publish" ${publishAllowed?'':'disabled'}>${row.status==='MODEL_PENDING'?'Resume operation':'Publish LOD1'}</button></div>
      <p class="lm-note">Готовая idle-поза, один mesh с именем lod1, одна UV, без костей. Для автоматической привязки нужен captured-idle bake.</p>
      <div class="actions"><button type="button" data-mnpc-action="align" ${alignAllowed?'':'disabled'}>Verify import &amp; alignment · Studio</button></div>
      <p class="lm-note">${row.alignment?`Geometry verified · Mesh ID ${esc(row.alignment.meshId)} · max error ${esc(row.alignment.maxVertexError.toFixed(4))} studs`:'Geometry alignment not verified'} · ${row.runtimeReady?'Runtime mesh':'Runtime red dummy'}. Проверка цвета/UV остаётся открытой.</p>
      <details><summary>Distance · ${row.inherits?'Inherited':'Override'}</summary>${profileFields('mnpc-actor',row.profile)}
        <div class="actions"><button type="button" data-mnpc-action="save-actor">Save override</button><button type="button" data-mnpc-action="inherit" ${row.inherits?'disabled':''}>Use defaults</button></div></details>
      <details><summary>Publication history</summary><div class="lm-revisions">${history}</div></details>`;
  }
  async function updateHistory() {
    const row=item();state.history=[];state.capture=null;
    if(row){state.history=(await request(`${path(row)}/history`,{cache:'no-store'})).items;state.capture=await request(`${path(row)}/capture`,{cache:'no-store'});}
  }
  function setBusy(value) {
    state.busy=value;
    $('lod-mnpc-panel').querySelectorAll('button,input,select').forEach(node=>{
      if(value){node.dataset.mnpcWasDisabled=String(node.disabled);node.disabled=true;}
      else if(node.dataset.mnpcWasDisabled!==undefined){node.disabled=node.dataset.mnpcWasDisabled==='true';delete node.dataset.mnpcWasDisabled;}
    });
  }
  async function run(fn, success, redraw=true) {
    if(state.busy)return;
    setBusy(true);message('Processing…');
    try {await fn();message(success||'');}
    catch(error){message(error.message);}
    finally {setBusy(false);if(redraw)render();}
  }
  async function reload() {
    const previous=item()?.fullFingerprint;
    state.data=await request(base,{cache:'no-store'});
    if(previous!==item()?.fullFingerprint)state.recipe.reviewedAssembly=false;
    await updateHistory();
  }
  async function load() {return run(async()=>{try{await reload();}catch(error){state.data=null;throw error;}},'');}
  $('mnpc-lod-refresh').addEventListener('click',load);
  $('mnpc-lod-search').addEventListener('input',renderRows);
  filter.addEventListener('change',()=>{try{window.localStorage?.setItem('game1.lod.mnpc.filter',filter.value);}catch(_){}renderRows();});
  $('mnpc-lod-rows').addEventListener('click',event=>{
    const button=event.target.closest('button[data-mnpc-edit]');if(!button||state.busy)return;
    state.selected=button.dataset.mnpcEdit;state.paths={fbx:'',texture:'',pose:'',poseAtlas:''};state.recipe={frame:1,targetTriangles:1000,textureSize:512,reviewedAssembly:false};state.history=[];
    return run(updateHistory,'');
  });
  $('mnpc-lod-editor').addEventListener('input',event=>{
    if(event.target.id==='mnpc-stage-fbx')state.paths.fbx=event.target.value;
    if(event.target.id==='mnpc-stage-texture')state.paths.texture=event.target.value;
    if(event.target.id==='mnpc-prepare-pose'||event.target.id==='mnpc-prepare-poseAtlas'){
      state.paths[event.target.id==='mnpc-prepare-pose'?'pose':'poseAtlas']=event.target.value;
      state.recipe.reviewedAssembly=false;$('mnpc-prepare-reviewedAssembly').checked=false;
    }
    const field=event.target.id?.replace(/^mnpc-(prepare|bake)-/,'');
    if(['frame','targetTriangles','textureSize'].includes(field))state.recipe[field]=event.target.value;
    if(field==='reviewedAssembly')state.recipe[field]=event.target.checked;
  });
  async function settings(row,profile) {
    state.data=await post(`${base}/settings`,{expectedRevision:state.data.settings.revision,
      kind:row?.kind||'',slug:row?.slug||'',profile});
  }
  $('mnpc-lod-defaults').addEventListener('click',event=>{
    if(!event.target.closest('button[data-mnpc-action="save-default"]'))return;
    return run(()=>settings(null,readProfile('mnpc-default')),'MNPC defaults saved. Runtime unchanged.');
  });
  $('mnpc-lod-editor').addEventListener('click',event=>{
    const button=event.target.closest('button[data-mnpc-action]'),row=item();if(!button||!row||state.busy)return;
    const action=button.dataset.mnpcAction;
    if(action==='close'){state.selected='';state.history=[];render();return;}
    if(action==='choose-fbx'||action==='choose-texture')return run(async()=>{
      const field=action==='choose-fbx'?'fbx':'texture';
      const chosen=await post(field==='fbx'?'/api/files/choose-location-asset-model':'/api/files/choose-character-atlas');
      if(chosen.path){state.paths[field]=chosen.path;$(`mnpc-stage-${field}`).value=chosen.path;}
    },'',false);
    if(action==='choose-pose'||action==='choose-pose-atlas')return run(async()=>{
      const field=action==='choose-pose'?'pose':'poseAtlas';
      const chosen=await post(field==='pose'?'/api/files/choose-location-asset-model':'/api/files/choose-character-atlas');
      if(chosen.path){state.paths[field]=chosen.path;$(`mnpc-prepare-${field}`).value=chosen.path;state.recipe.reviewedAssembly=false;$('mnpc-prepare-reviewedAssembly').checked=false;}
    },'',false);
    if(action==='capture')return run(async()=>{
      try {state.capture=await post(`${path(row)}/capture`,{expectedRevision:row.revision,fullFingerprint:row.fullFingerprint,phase:0.35,includeGeometry:true});}
      catch(error){try{await reload();}catch(_){state.data=null;}throw error;}
    },'Idle geometry captured. No Cloud changes.');
    if(action==='bake')return run(async()=>{
      try {
        await post(`${path(row)}/bake`,{expectedRevision:row.revision,fullFingerprint:row.fullFingerprint,
          captureSha256:state.capture?.captureSha256,targetTriangles:Number($('mnpc-bake-targetTriangles').value),textureSize:Number($('mnpc-bake-textureSize').value)});
      }catch(error){try{await reload();}catch(_){state.data=null;}throw error;}
      await reload();
    },'Captured LOD1 baked and staged. No Cloud upload.');
    if(action==='prepare')return run(async()=>{
      const integer=field=>{const raw=String($(`mnpc-prepare-${field}`).value);const n=Number(raw);if(!raw.trim()||!Number.isSafeInteger(n))throw Error('Введите целое число: '+field);return n;};
      try {
        await post(`${path(row)}/prepare`,{posePath:state.paths.pose,texturePath:state.paths.poseAtlas,
          frame:integer('frame'),targetTriangles:integer('targetTriangles'),textureSize:integer('textureSize'),
          reviewedAssembly:$('mnpc-prepare-reviewedAssembly').checked,expectedRevision:row.revision,fullFingerprint:row.fullFingerprint});
      }catch(error){try{await reload();}catch(_){state.data=null;}throw error;}
      await reload();
    },'LOD1 generated and staged. No Cloud upload.');
    if(action==='save-actor')return run(()=>settings(row,readProfile('mnpc-actor')),'MNPC override saved. Runtime unchanged.');
    if(action==='inherit')return run(()=>settings(row,null),'Inherited defaults. Runtime unchanged.');
    if(action==='align')return run(async()=>{
      try {await post(`${path(row)}/align`,{expectedRevision:row.revision});}
      catch(error){try{await reload();}catch(_){state.data=null;}throw error;}
      await reload();
    },'Published geometry alignment verified. Runtime unchanged.');
    if(action==='stage'||action==='publish')return run(async()=>{
      try {
        await post(`${path(row)}/${action}`,action==='stage'?{sourcePath:state.paths.fbx,texturePath:state.paths.texture,
          expectedRevision:row.revision,fullFingerprint:row.fullFingerprint}:{expectedRevision:row.revision});
      } catch(error) { // Partial Cloud successes must be visible after an error.
        try {await reload();} catch (_) {state.data=null;}
        throw error;
      }
      await reload();
    },action==='stage'?'LOD1 staged. No Cloud upload.':'Publication updated. Runtime unchanged.');
  });
  window.game1MnpcLod={load};
})();
