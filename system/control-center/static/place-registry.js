/* M241 · Location-only Place Registry, UI ownership only. No independent Sync mechanism. */
(() => {
  const byId = id => document.getElementById(id);
  const html = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const endpoint = '/api/location-place-registry';
  const source = {scan:null,stale:false,busy:false,loaded:false,expanded:null};
  const $status = message => {byId('pr-status').textContent = message;};
  const $action = message => {byId('pr-action-status').textContent = message;};
  const active = () => !!source.scan && !source.stale && !source.busy;
  const groups = () => (source.scan?.placements || []).reduce((acc,row) => {
    (acc[row.slug] ||= []).push(row);return acc;
  }, {});
  const needsRepair = row => row.canRepair === true && !row.requiresRepublish && !row.ambiguous && (row.needsStructure || row.duplicateId);
  const needsSync = row => row.canSync && (row.needsMesh || row.needsRig || row.needsTexture || row.needsMaterial || row.needsAlpha);

  function buttons() {
    for (const name of ['pr-scan','pr-select-all','pr-repair-all','pr-sync-all']) {
      const button = byId(name);
      if (!button) continue;
      const write = name === 'pr-repair-all' || name === 'pr-sync-all';
      button.disabled = source.busy || (name !== 'pr-scan' && !active()) ||
        (write && (source.scan?.incomplete || !byId('pr-backup').checked ||
          (name === 'pr-repair-all' && !(source.scan?.placements || []).some(needsRepair))));
    }
    for (const button of byId('pr-groups').querySelectorAll('button[data-pr-action]')) {
      const write = button.dataset.prAction !== 'select';
      button.disabled = !active() || (write && (source.scan?.incomplete || !byId('pr-backup').checked || button.dataset.prBlocked==='true'));
    }
  }

  function snapshotViewport() {
    const scrolls={};
    for(const rows of byId('pr-groups').querySelectorAll('.pr-rows')) {
      const slug = rows.closest('details')?.dataset.group;
      if(slug) scrolls[slug]=rows.scrollTop;
    }
    return {x:window.scrollX,y:window.scrollY,scrolls};
  }
  function restoreViewport(position) {
    requestAnimationFrame(()=>{
      for (const rows of byId('pr-groups').querySelectorAll('.pr-rows')) {
        const slug=rows.closest('details')?.dataset.group;
        if (slug in position.scrolls) rows.scrollTop=position.scrolls[slug];
      }
      window.scrollTo(position.x,position.y);
    });
  }

  function item(row) {
    const issues=(row.issues || []).map(v=>`<span class="pr-warning">${html(v)}</span>`).join('');
    const repair=needsRepair(row),sync=needsSync(row);
    return `<div class="pr-item${row.ambiguous?' pr-ambiguous':''}">
      <div class="pr-item-heading"><strong>${html(row.name)}</strong>
        <code>${html(row.key)} · ${html(row.placementId || 'нет Placement ID')}</code></div>
      <div class="pr-path" title="${html(row.path)}">${html(row.path)}</div>
      <div class="pr-status-row"><span class="${row.needsMesh?'pr-old':'pr-ok'}">Mesh ${row.needsMesh?'✕ устарел':'✓ актуален'}</span>
        <span class="${row.needsTexture?'pr-old':'pr-ok'}">Texture ${row.needsTexture?'✕ устарела':'✓ актуальна'}</span>
        ${row.needsRig?'<span class="pr-old">Rig ✕ отличается состав MeshPart</span>':''}
        ${row.needsMaterial?'<span class="pr-old">Материал ✕ требует Sync</span>':''}
        ${row.needsAlpha?'<span class="pr-old">Alpha ✕ требует Sync</span>':''}
        <small>Mesh ID ${html(row.meshId)} · Texture ID ${html(row.textureId||'—')}</small></div>
      ${issues?`<div class="pr-issues">${issues}</div>`:''}
      <div class="actions"><button type="button" data-pr-action="select" data-key="${html(row.key)}">Select in Studio</button>
        <button type="button" data-pr-action="repair" data-key="${html(row.key)}" data-pr-blocked="${!repair}">Repair</button>
        <button type="button" data-pr-action="sync" data-key="${html(row.key)}" data-pr-blocked="${!sync}">Sync</button></div></div>`;
  }

  function render() {
    const data=source.scan,box=byId('pr-groups'),metrics=byId('pr-metrics');
    if (!data) {
      box.innerHTML='<p class="hint">Нет сканирования. Нажми Scan Place.</p>';
      metrics.replaceChildren();buttons();return;
    }
    const s=data.summary;
    metrics.innerHTML=[['Размещений',s.placements],['Mesh / rig',s.outdatedMesh],
      ['Texture устарела',s.outdatedTexture],['Материал',s.outdatedMaterial],['Alpha',s.outdatedAlpha],['Структура',s.structure],
      ['Повтор ID',s.duplicateIds],['Неоднозначно',s.ambiguous]].map(([n,v])=>
      `<div class="pr-metric"><b>${Number(v)||0}</b><span>${html(n)}</span></div>`).join('');
    const entries=Object.entries(groups()).sort((a,b)=>a[0].localeCompare(b[0]));
    if(source.expanded===null) source.expanded=new Set(entries.slice(0,1).map(([slug])=>slug));
    box.innerHTML=entries.map(([slug,rows])=>{
      const repairs=rows.filter(needsRepair).length;
      const syncs=rows.filter(needsSync).length;
      return `<details data-group="${html(slug)}" ${source.expanded.has(slug)?'open':''}>
        <summary><b>${html(slug)}</b><span>${rows.length} размещений · Repair ${repairs} · Sync ${syncs}</span></summary>
        <div class="pr-group-content"><div class="pr-group-actions">
          <button type="button" data-pr-action="repair-group" data-group="${html(slug)}"
            data-pr-blocked="${repairs===0}">Repair group (${repairs})</button>
          <button type="button" data-pr-action="sync-group" data-group="${html(slug)}"
            data-pr-blocked="${syncs===0}">Sync group (${syncs})</button>
          <small>Только ${html(slug)} · Repair исправляет структуру, Sync обновляет устаревшие ресурсы</small></div>
          <div class="pr-rows">${rows.map(item).join('')}</div></div></details>`;
    }).join('');
    buttons();
  }

  async function loadRevisions() {
    try {
      const data=await request(endpoint+'/revisions?limit=30');
      const rows=data.revisions||[];
      byId('pr-revisions').innerHTML=rows.length?rows.map((r,i)=>
        `<div class="pr-revision-row"><button class="pr-revision" type="button" data-revision="${r.id}">
          <b>#${r.id}</b> · ${new Date(r.recorded_utc*1000).toLocaleString('ru-RU')}
          · ${r.total} декораций · ${r.issues} предупреждений</button>
          ${i+1<rows.length?`<button type="button" data-compare="${rows[i+1].id}:${r.id}">Сравнить</button>`:''}
          <button type="button" data-download="${r.id}">JSON</button></div>`).join(''):
          '<p class="hint">Нет сохранённых ревизий.</p>';
    } catch(error) {byId('pr-revisions').textContent=error.message;}
  }

  async function loadActions() {
    try {
      const data=await request(endpoint+'/actions?limit=40');
      const rows=data.actions || [];
      byId('pr-action-log').innerHTML=rows.length?rows.map(r=>{
        const title=r.action==='repair'?'Repair':'Sync';
        const selected=r.selected||[];
        const slugs=[...new Set(selected.map(x=>x.slug))];
        const scope=selected.length?`${selected.length} размещений · ${slugs.join(', ')}`:'Запись старого формата';
        const skipped=Array.isArray(r.report?.skipped)?r.report.skipped:[];
        const colCount=Number(r.report?.collidersCreated)||0;
        const status=r.status==='undone'?'Отменено':
          r.status==='no_changes'?(skipped.length?'Пропущено':'Без изменений'):
          r.status==='legacy'?'До M241':'Применено';
        const skippedDetails=skipped.length?
          `<small class="pr-log-skipped">Причины пропуска (${skipped.length}): ${skipped.map(html).join('; ')}</small>`:'';
        return `<div class="pr-action-row"><div class="pr-action-info">
          <strong>#${html(r.id)} · ${title} · ${new Date(r.recordedUtc*1000).toLocaleString('ru-RU')}</strong>
          <small>${html(scope)} · изменено ${r.affected} · перед ревизией #${r.beforeRevision}</small>
          <span class="pr-state${r.status==='undone'?' pr-state-undone':''}">${status}</span>
          ${colCount?`<small>Восстановлено COL: ${colCount}</small>`:''}
          ${skippedDetails}</div>
          ${r.status==='applied'?`<button type="button" data-pr-undo="${r.id}" ${r.canUndo?'':'disabled title="Сначала отмените более новые операции"'}>Undo</button>`:''}
        </div>`;
      }).join(''):'<p class="hint">Журнал пуст. Repair и Sync будут появляться здесь автоматически.</p>';
      buttons();
    } catch(error){byId('pr-action-log').textContent='Не удалось загрузить журнал: '+error.message;}
  }

  async function scan({automatic=false}={}) {
    const position=snapshotViewport();
    if(!automatic) $status('Сканирование опубликованных Mesh ID и дерева Studio…');
    const reply=await request(endpoint,{method:'POST',body:JSON.stringify({phase:'scan'})});
    const data=reply.studio;
    if(!data || !Array.isArray(data.placements)) throw new Error('Некорректный ответ сканирования Studio');
    source.scan=data;source.stale=false;
    render();restoreViewport(position);
    $status(`Ревизия #${data.revision?.revisionId}: ${data.summary.placements} размещений.`+
      (data.revision?.unchanged?' Без изменений.':' Снимок сохранён.'));
    if(data.warnings?.length) $action('Скан неполный: '+data.warnings.join('; ')+'. Repair/Sync заблокированы.');
    await Promise.all([loadRevisions(),loadActions()]);
  }

  async function run(phase,keys=[],actionId=null) {
    if(source.busy) return;
    source.busy=true;buttons();
    if(phase!=='scan') $action(phase==='select'?'Выделение в Studio…':
      phase==='undo'?'Отмена последней операции Studio…':`${phase.toUpperCase()} в Studio…`);
    try {
      if(phase==='scan') await scan();
      else {
        const reply=await request(endpoint,{method:'POST',body:JSON.stringify({
          phase,scanToken:source.scan?.scanToken || '',keys,
          ...(phase==='undo'?{actionId}:{})})});
        const data=reply.studio;
        $action(phase==='undo'?'Undo выполнен в Studio.':
          `Готово: ${data.changed ?? data.selected ?? 0} · ${data.note || ''}`+
          (data.skipped?.length?` · Пропущено: ${data.skipped.join('; ')}`:''));
        if(phase==='repair'||phase==='sync'||phase==='undo') {
          // On a committed mutation the old Studio scan token is invalid.
          // Rescan transparently; keep the currently visible rows and viewport.
          source.stale=true;
          await scan({automatic:true});
        }
      }
    } catch(error) {
      $action(`Ошибка ${phase}: ${error.message}`);
      if(source.stale) {
        $status('Не удалось обновить состояние. Данные ниже сохранены для просмотра, но требуют Scan Place.');
        await Promise.all([loadRevisions(),loadActions()]);
      }
      else if(phase==='scan') $status('Ошибка сканирования: '+error.message);
    } finally {source.busy=false;buttons();}
  }

  function mutate(phase,keys,description) {
    if(!active()) return $action('Сначала выполни Scan Place.');
    if(keys.length===0) return $action(phase==='repair'?'Нет нарушений структуры для Repair.':'Все подходящие ресурсы актуальны.');
    if(source.scan.incomplete) return $action('Неполное сканирование: изменения заблокированы.');
    if(!byId('pr-backup').checked) return $action('Подтверди резервную копию .rbxl в верхней части раздела.');
    const details=phase==='repair'?'Исправление модели и Placement ID, без изменения CFrame':
      'Замена только однозначно распознанных опубликованных ресурсов';
    if(!confirm(`${phase.toUpperCase()} · ${description || keys.length+' размещений'}\n${details}.\n\nПродолжить?`)) return;
    run(phase,keys);
  }

  byId('pr-scan').onclick=()=>run('scan');
  byId('pr-select-all').onclick=()=>active() && run('select',source.scan.placements.map(p=>p.key));
  byId('pr-repair-all').onclick=()=>active()&&mutate('repair',source.scan.placements.filter(needsRepair).map(p=>p.key),'все группы');
  byId('pr-sync-all').onclick=()=>active()&&mutate('sync',source.scan.placements.filter(needsSync).map(p=>p.key),'все группы');
  byId('pr-backup').onchange=buttons;
  byId('pr-groups').addEventListener('toggle',event=>{
    const group=event.target;
    if(group.tagName!=='DETAILS'||!group.dataset.group||source.expanded===null) return;
    if(group.open)source.expanded.add(group.dataset.group);else source.expanded.delete(group.dataset.group);
  },true);
  byId('pr-groups').addEventListener('click',event=>{
    const button=event.target.closest('button[data-pr-action]');
    if(!button||!active())return;
    const {prAction:phase,key,group}=button.dataset;
    if(phase==='repair-group'||phase==='sync-group') {
      const isRepair=phase==='repair-group';
      const keys=(groups()[group]||[]).filter(isRepair?needsRepair:needsSync).map(r=>r.key);
      mutate(isRepair?'repair':'sync',keys,`${group} · ${keys.length} размещений`);
    } else if(phase==='select')run('select',[key]);
    else mutate(phase,[key],`размещение ${key}`);
  });
  byId('pr-action-log').addEventListener('click',event=>{
    const button=event.target.closest('button[data-pr-undo]');
    if(!button||source.busy)return;
    const id=Number(button.dataset.prUndo);
    if(!Number.isSafeInteger(id)||id<1)return;
    if(confirm('Отменить эту операцию через историю Roblox Studio?\nЕсли после неё были другие изменения Studio, Undo будет заблокирован.'))run('undo',[],id);
  });
  byId('pr-refresh-actions').onclick=loadActions;
  byId('pr-revisions').addEventListener('click',async event=>{
    const button=event.target.closest('button');if(!button)return;
    try {
      const pre=byId('pr-revision-details');
      if(button.dataset.compare) {
        const [before,after]=button.dataset.compare.split(':');
        const diff=await request(`${endpoint}/diff?before=${before}&after=${after}`);
        pre.hidden=false;pre.textContent=`Ревизия #${before} → #${after}: новых/изменённых ${diff.added}, прежних/изменённых ${diff.removed}.`;
        return;
      }
      const id=button.dataset.download||button.dataset.revision;if(!id)return;
      const data=await request(`${endpoint}/revisions/${id}`);
      if(button.dataset.download) {
        const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
        const url=URL.createObjectURL(blob),anchor=document.createElement('a');
        anchor.href=url;anchor.download=`game1_location_place_revision_${id}.json`;
        document.body.append(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);return;
      }
      pre.hidden=false;
      pre.textContent=JSON.stringify({schemaVersion:data.schemaVersion,placeId:data.placeId,
        registeredLocations:data.placements.length,locations:data.placements.map(v=>({
          path:v.path,slug:v.slug,placementId:v.placementId,meshId:v.meshId,
          textureId:v.textureId,issues:v.issues}))},null,2);
    } catch(error){$action(error.message);}
  });
  byId('pr-refresh-revisions').onclick=loadRevisions;
  byId('pr-auto-scan').checked=(()=>{try{return localStorage.getItem('game1.placeRegistry.autoScan')==='1'}catch{return false}})();
  byId('pr-auto-scan').onchange=()=>{try{localStorage.setItem('game1.placeRegistry.autoScan',byId('pr-auto-scan').checked?'1':'0')}catch{}};
  setInterval(()=>{
    if(byId('pr-auto-scan').checked&&!source.busy&&!document.hidden&&state.view==='place-registry')run('scan');
  },600000);
  window.game1PlaceRegistryLoad=()=>{
    if(!source.loaded){source.loaded=true;Promise.all([loadRevisions(),loadActions()]);}
    buttons();
  };
  if(state.view==='place-registry')window.game1PlaceRegistryLoad();
})();
