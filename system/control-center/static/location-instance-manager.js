/* Instance Manager · collision inspection is a required, token-bound stage before Replace. */
(() => {
  const id = key => document.getElementById(key);
  const state = {busy:false, preview:null, inspected:null, assets:[], pendingClear:Promise.resolve()};
  const fields = ['li-source','li-target','li-scope'];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const status = text => {id('li-status').textContent = text;};
  const disable = busy => {
    state.busy=busy;
    id('li-preview').disabled=busy;
    id('li-inspect').disabled=busy || !state.preview;
    id('li-clear-preview').disabled=busy || !state.inspected;
    const acceptable=!!state.inspected && (state.inspected.warnings===0 || id('li-approve-shear').checked);
    id('li-replace').disabled=busy || !acceptable;
  };
  const clearAnchors = () => id('li-anchor').replaceChildren(new Option('Pivot новой Model','model'));
  function loadAnchors(options) {
    const anchor=id('li-anchor');anchor.replaceChildren();
    for(const option of options)anchor.add(new Option(option.label,option.id));
    anchor.value=options.some(option => option.id === 'geometry') ? 'geometry' : 'model';
  }
  function discardInspection() {
    const token=state.preview?.token;
    const old=state.inspected;
    state.inspected=null;
    id('li-collision-approval').hidden=true;
    id('li-collision-warnings').replaceChildren();
    disable(state.busy);
    // Cleanup is bound to the exact inspection token, never just the placement
    // scan token. A delayed Clear cannot erase a newer 3-D inspection.
    if(old && token) state.pendingClear=state.pendingClear.then(() =>
      send('clear',token,old.token).catch(()=>{}));
  }
  function reset() {
    discardInspection(); state.preview=null; clearAnchors();
    id('li-approve-shear').checked=false;
    id('li-placements').textContent='Сначала Preview.';
    disable(state.busy);
    if(!state.busy) status('Настройки изменились. Выполни Preview заново.');
  }
  const catalogKey = rows => JSON.stringify(rows.map(row => [
    row.slug,row.status,row.model_asset_id,row.model_published_sha256,
    row.collisionBlueprintRevision,row.collisionBlueprintSha256,row.revision,
    row.appearanceMode,row.visualMaterial,row.visualColor,
  ]).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))));
  function refresh(rows) {
    const nextAssets=(rows || []).filter(row => ['PUBLISHED','UPDATE_AVAILABLE'].includes(row.status) && row.model_asset_id);
    // Stable publication identity instead of entire API rows: changing list
    // order or unrelated UI metadata must not invalidate an inspected token.
    // Real model/Blueprint revisions still revoke the placement Preview.
    const unchanged=catalogKey(state.assets)===catalogKey(nextAssets);
    state.assets=nextAssets;
    for(const field of ['li-source','li-target']) {
      const select=id(field),remembered=select.value;
      select.replaceChildren(new Option('Выбери опубликованный ассет',''));
      for(const row of state.assets) {
        if(field==='li-target' && row.status!=='PUBLISHED') continue;
        select.add(new Option(`${row.slug} · ${row.model_asset_id}`,row.slug));
      }
      select.value=[...select.options].some(opt=>opt.value===remembered)?remembered:'';
    }
    if(!unchanged)reset();
  }
  async function send(phase,token,inspectionToken='',approveShear=false,focus=null) {
    const response=await fetch('/api/location-instance-manager',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({phase,sourceSlug:id('li-source').value,targetSlug:id('li-target').value,
        scope:id('li-scope').value,scanToken:token,anchorId:id('li-anchor').value,
        inspectionToken,approveShear,
        ...(focus ? {focusIndex:focus.index,focusPartId:focus.partId} : {})}),
    });
    let data={};try{data=await response.json();}catch{}
    if(!response.ok) throw Error(data.error || `HTTP ${response.status}`);
    return data.studio;
  }
  function showChoiceStatus() {
    const p=state.preview;if(!p)return;
    const sourceAnchor=id('li-anchor').value==='geometry'?'Геометрия исходного MeshPart (CFrame) ← ':'Pivot исходной Model ← ';
    status(`${p.count} Model: ${p.source} → ${p.target}. ${sourceAnchor}${id('li-anchor').selectedOptions[0]?.textContent}.
`+
      `Исторический Pivot: ${p.normalizedPivots}; ручной MeshPart.Size: ${p.preservedManualSizes}; конфликтующих ID: ${p.reassignedIds}.
`+
      `${p.differingVisualAxes ? `Различаются оси Model/MeshPart: ${p.differingVisualAxes}.
`:''}`+
      'Следующий шаг: Show collision preview. Зелёные коллизии допустимы; оранжевые — увеличены или приближены (включая клинья). Place пока не изменён.');
  }
  async function preview() {
    if(state.busy)return;
    const source=id('li-source').value,target=id('li-target').value;
    if(!source||!target||source===target){status('Выбери два разных опубликованных Location Assets.');return;}
    discardInspection();state.preview=null;clearAnchors();disable(true);
    status('Проверка размещений и Pivot новой модели…');
    try {
      await state.pendingClear;
      const data=await send('preview','');
      if(!data.scanToken||!Array.isArray(data.placements)||data.count!==data.placements.length||
        !Array.isArray(data.anchorOptions)||data.anchorOptions[0]?.id!=='model')
        throw Error('Studio вернула неполный Preview');
      loadAnchors(data.anchorOptions);
      state.preview={token:data.scanToken,source,target,scope:id('li-scope').value,
        count:data.count,reassignedIds:data.reassignedIds||0,normalizedPivots:data.normalizedPivots||0,
        preservedManualSizes:data.preservedManualSizes||0,differingVisualAxes:data.differingVisualAxes||0};
      id('li-placements').innerHTML=data.placements.map(row=>
        `<div class="location-instance-placement"><b>${escape(row.name)}</b> · ${escape(row.placementId)}`+
        `${row.newPlacementId&&row.newPlacementId!==row.placementId?` <strong>→ ${escape(row.newPlacementId)}</strong>`:''}`+
        `<small>${escape(row.path)}${row.legacyPivot?' · исторический Pivot':''}${row.manualSize?' · изменённый Size':''}</small></div>`).join('');
      showChoiceStatus();
    }catch(error){clearAnchors();status('Preview: '+error.message);id('li-placements').textContent='Ничего не выбрано.';}
    finally{disable(false);}
  }
  async function inspect() {
    if(state.busy||!state.preview)return;
    discardInspection();disable(true);
    status('Studio строит временный 3D-предпросмотр всех рассчитанных Collision Parts…');
    try {
      await state.pendingClear;
      const data=await send('inspect',state.preview.token);
      if(!data.inspectionToken||!Number.isInteger(data.warnings)||!Array.isArray(data.warningDetails))
        throw Error('Studio вернула неполный Collision Preview');
      state.inspected={token:data.inspectionToken,warnings:data.warnings,anchor:id('li-anchor').value};
      id('li-collision-approval').hidden=data.warnings===0;
      id('li-collision-warning-count').textContent=`Были бы заблокированы: ${data.warnings}`;
      id('li-collision-warnings').innerHTML=data.warningDetails.map(row=>
        `<div class="location-instance-placement"><b>${escape(row.partId)}</b>`+
        `<small>${escape(row.path)} · ${row.approximate ? "ПРИБЛИЖЕНИЕ · " : ""}${escape(row.shape||"Block")} · добавлено ${escape(row.excessStuds.map(n=>n.toFixed(2)).join(' / '))} studs `+
        `(${escape(row.addedPercent.map(n=>n.toFixed(1)).join(' / '))}%) по X/Y/Z${row.approximate ? " · Наклон/контур могут отличаться!" : ""}</small>`+
        (Number.isInteger(row.index) ? `<div class="location-instance-warning-actions">`+
          `<button type="button" data-li-focus-index="${row.index}" data-li-focus-part="${escape(row.partId)}">Показать в Studio</button></div>` : '')+
        `</div>`).join('');
      status(`Предпросмотр в Studio: ${data.collisionParts} Collision Parts, превышений: ${data.warnings}.
`+
        'ЗЕЛЁНЫЕ — точные/допустимые; ОРАНЖЕВЫЕ — увеличенные блоки или ПРИБЛИЖЁННЫЕ клинья/кривые формы.\n'+
        (data.warnings?'Проблемные объекты показаны списком. Осмотри их в Studio и включи «Игнорировать ограничения», если форма устраивает.':'Все коллизии соответствуют обычным пределам. Можно подтвердить замену.')+
        '\nАвторские Model не изменены. Удали предпросмотр перед сохранением Place; он исчезнет автоматически через 5 минут.');
    }catch(error){status('Collision Preview: '+error.message+'\nPlace не изменён.');}
    finally{disable(false);}
  }
  async function focusWarning(index,partId) {
    const p=state.preview, inspection=state.inspected;
    if(state.busy||!p||!inspection||!Number.isInteger(index)||index<1||!partId)return;
    disable(true);
    try {
      await send('focus',p.token,inspection.token,false,{index,partId});
      status(`Studio: камера наведена на проблемную коллизию ${partId} (${index}/${p.count}).\n`+
        'Выделение исходных моделей не изменено. Предпросмотр и подтверждение остаются действительными.');
    }catch(error){status('Показать в Studio: '+error.message+'\nИсходный Place не изменён.');}
    finally{disable(false);}
  }
  async function clearPreview() {
    if(state.busy||!state.preview||!state.inspected)return;
    disable(true);
    try{await send('clear',state.preview.token,state.inspected.token);status('3D-предпросмотр удалён. Для замены проведи проверку заново.');}
    catch(error){status('Clear Preview: '+error.message);}
    finally{state.inspected=null;id('li-approve-shear').checked=false;id('li-collision-approval').hidden=true;disable(false);}
  }
  async function replace() {
    const p=state.preview,i=state.inspected;
    if(state.busy||!p||!i||i.anchor!==id('li-anchor').value||
      p.source!==id('li-source').value||p.target!==id('li-target').value||p.scope!==id('li-scope').value||
      (i.warnings>0&&!id('li-approve-shear').checked))return;
    if(!confirm(`Заменить ${p.count} Model?
${p.source} → ${p.target}
`+
      `В Studio показаны ${i.warnings} увеличенных или ПРИБЛИЖЁННЫХ коллизий, остальные — зелёные.
`+
      (id('li-approve-shear').checked ? 'ВНИМАНИЕ: подтверждены увеличенные/ПРИБЛИЖЁННЫЕ формы; наклон/контур могут отличаться.\n' : '')+
      'Изменения коснутся только выбранных размещений. Undo — Ctrl+Z; предварительно сохрани Place.'))return;
    disable(true);status('Studio проверяет совпадение с 3D-предпросмотром и заменяет Model…');
    try {
      const result=await send('replace',p.token,i.token,id('li-approve-shear').checked);
      status(`Заменено ${result.changed} из ${p.count} Model. Переиздано Placement ID: ${result.reassignedIds||0}.
${result.note||''}
`+
        'Сохрани Place. Повтори Place Registry Scan.');
      id('li-placements').textContent='Замена завершена. Новый Preview покажет текущее состояние.';
      state.preview=null;state.inspected=null;
      id('li-collision-approval').hidden=true;
      id('li-approve-shear').checked=false;
    }catch(error){
      const message=String(error.message||error);
      if(message.includes('Collision preview not active in Studio') ||
         message.includes('Collision inspection token is stale')) {
        // Studio kept the placement Preview session. Only the 3D inspection
        // was lost, so the user can press Show again without a full rescan.
        state.inspected=null;
        id('li-collision-approval').hidden=true;
        id('li-collision-warnings').replaceChildren();
        status(`3D-предпросмотр потерян. Исходные Model не изменены.\n${message}\n`+
          'Нажми Show collision preview · Studio ещё раз, осмотри коллизии и затем повтори Replace.');
      } else if(message.includes('Check the explicit oversized-collision approval')) {
        status('Замена не выполнена. Поставь галочку согласия с оранжевыми коллизиями и повтори Replace.');
      } else {
        // For all other errors, don't reuse potentially invalid scan evidence.
        state.preview=null;
        state.inspected=null;
        id('li-approve-shear').checked=false;
        id('li-collision-approval').hidden=true;
        id('li-collision-warnings').replaceChildren();
        status('Replace: '+message+'\nИсходные Model должны остаться неизменными. Начни с Preview replacements.');
      }
    }
    finally{disable(false);}
  }
  for(const field of fields)id(field).addEventListener('change',reset);
  id('li-anchor').addEventListener('change', discardInspection);
  id('li-anchor').addEventListener('change', showChoiceStatus);
  id('li-approve-shear').addEventListener('change',()=>disable(state.busy));
  id('li-collision-warnings').addEventListener('click', event => {
    const button=event.target.closest('[data-li-focus-index]');
    if(!button)return;
    focusWarning(Number(button.dataset.liFocusIndex),button.dataset.liFocusPart);
  });
  id('li-preview').addEventListener('click',preview);
  id('li-inspect').addEventListener('click',inspect);
  id('li-clear-preview').addEventListener('click',clearPreview);
  id('li-replace').addEventListener('click',replace);
  window.game1LocationInstanceRefresh=refresh;
})();
