/* LOD Manager: authoritative Place Registry inventory + project-owned streaming policy. */
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = {overview:null, busy:false, filter:'all', term:'', preflight:null, domain:'location',
    expandedHouses:new Set(), collapsedGroups:new Set(), houseTerm:'', houseFilter:'all',
    partEdits:new Map(), partMessages:new Map(), assetEdits:new Map(), assetMessages:new Map()};
  const defaultSettings = {
    hysteresis:10,
    workspace:{streamingEnabled:true,minRadius:64,targetRadius:1024,
      modelStreamingBehavior:'Improved',streamingIntegrityMode:'PauseOutsideLoadedArea',streamOutBehavior:'Opportunistic'}
  };
  const helpIds = ['lod-distance-hysteresis',
    'lod-workspace-enabled','lod-workspace-min-radius','lod-workspace-target-radius',
    'lod-workspace-model','lod-workspace-integrity','lod-workspace-streamout'];
  function fillSettings(settings) {
    const w=settings.workspace;
    $('lod-distance-hysteresis').value=String(settings.hysteresis);
    $('lod-workspace-enabled').checked=w.streamingEnabled;
    $('lod-workspace-min-radius').value=String(w.minRadius); $('lod-workspace-target-radius').value=String(w.targetRadius);
    $('lod-workspace-model').value=w.modelStreamingBehavior;
    $('lod-workspace-integrity').value=w.streamingIntegrityMode;
    $('lod-workspace-streamout').value=w.streamOutBehavior;
  }
  function readSettings() {
    const integer = id => {
      const el=$(id), n=Number(el.value);
      if (!el.value.trim() || !Number.isSafeInteger(n)) throw Error(`${id}: введите целое число studs`);
      return n;
    };
    const hysteresis=integer('lod-distance-hysteresis');
    if(hysteresis<0 || hysteresis>100)throw Error('Гистерезис: 0–100 studs');
    const w={streamingEnabled:$('lod-workspace-enabled').checked,
      minRadius:integer('lod-workspace-min-radius'),targetRadius:integer('lod-workspace-target-radius'),
      modelStreamingBehavior:$('lod-workspace-model').value,
      streamingIntegrityMode:$('lod-workspace-integrity').value,streamOutBehavior:$('lod-workspace-streamout').value};
    if(w.minRadius<32 || w.minRadius>512 || w.targetRadius<96 || w.targetRadius>4096 || w.targetRadius<=w.minRadius)
      throw Error('Workspace: Min 32–512, Target 96–4096 и Target > Min');
    return {hysteresis,workspace:w};
  }
  async function saveSettings(payload) {
    if (state.busy) return;
    state.busy=true;
    $('lod-settings-status').textContent='Сохраняем настройки проекта…';
    try {
      const view=await request('/api/lod-manager/settings', {method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      state.overview=view; state.preflight=null;
      $('lod-build-execute').hidden=true;
      $('lod-build-preview').hidden=true;
      $('lod-build-status').textContent='Настройки изменены. Запусти Preflight по новому профилю.';
      $('lod-settings-status').textContent='Сохранено. Studio Play получает визуальные LOD-настройки автоматически; для Runtime нужен новый Preflight.';
      fillSettings(view.settings);
      for(const [slug, mode] of Object.entries(payload.modes||{})){
        if(state.assetEdits.has(slug))state.assetEdits.set(slug,{...state.assetEdits.get(slug),mode});
      }
      if(Object.hasOwn(payload,'hysteresis'))state.partMessages.clear();
      return true;
    } catch(error) {
      $('lod-settings-status').textContent=`Не сохранено: ${error.message}`;
      return false;
    } finally {state.busy=false;render();}
  }

  async function saveHouseProfile(slug, values) {
    if(state.busy || !state.overview)return;
    const house=(state.overview.realEstate?.items||[]).find(h=>h.slug===slug);
    if(!house || !house.profile)return;
    const old=house.profile;
    state.busy=true;
    $('lod-settings-status').textContent=`${slug}: сохраняем Runtime Profile…`;
    try {
      await request(`/api/real-estate/${encodeURIComponent(slug)}/runtime-profile`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({profile:values,expectedRevision:old.revision})});
      state.overview=await request('/api/lod-manager');
      state.preflight=null;
      $('lod-build-preview').hidden=true;
      $('lod-build-execute').hidden=true;
      $('lod-build-status').textContent='Профиль дома изменён — нужен новый Preflight и Runtime Draft.';
      $('lod-settings-status').textContent=`${slug}: профиль сохранён; Studio Play обновится автоматически.`;
    } catch(error) {
      $('lod-settings-status').textContent=`${slug}: ${error.message}`;
    } finally {state.busy=false;render();}
  }

  function saveHouseMode(slug, mode) {
    saveHouseProfile(slug,{mode});
  }
  // Presentation-only groupings; arbitrary authored mesh names remain visible.
  const housePartGroups = [
    ['foundation','Основа',/^(house|ground|foundation|floor|floors)(_|$)/],
    ['walls','Стены и конструкции',/^(walls?|stone_structures|wooden_structures)(_|$)/],
    ['exterior','Крыша и проёмы',/^(roof|chimney|window|door)(_|$)/],
    ['details','Интерьер и декор',/^(fireplace|flowerbed|plants?|restoration)(_|$)/],
  ];
  function groupHouseParts(parts) {
    const groups=new Map([...housePartGroups.map(([key,label])=>[key,{key,label,parts:[]}]),
      ['other',{key:'other',label:'Другие части',parts:[]}]]);
    for(const part of parts) {
      const key=housePartGroups.find(([, ,test])=>test.test(part.name.toLowerCase()))?.[0]||'other';
      groups.get(key).parts.push(part);
    }
    return [...groups.values()].filter(group=>group.parts.length);
  }

  const partKey = (slug,part) => JSON.stringify([slug,part]);
  const partRecord = (overview,slug,part) => overview?.realEstate?.items
    ?.find(h=>h.slug===slug)?.partStreaming?.[part];
  function readPartFields(section) {
    return Object.fromEntries(['lod1','hide'].map(key=>[
      key,section.querySelector(`[data-part-distance="${key}"]`)?.value??'']));
  }
  // Mirror the server's edit normalization; persisted/runtime validation stays strict.
  function normalizePartEdit(raw) {
    const values=Object.fromEntries(Object.entries(raw).map(([name,value])=>[name,Number(value)]));
    if(Object.keys(raw).some(name=>!raw[name].trim() || !Number.isSafeInteger(values[name])))
      throw Error('Введи целые числа studs.');
    if(values.lod1<20 || values.hide<1 || values.hide>10000)
      throw Error('LOD1 ≥ 20; UNLOADED от 1 до 10000 studs.');
    const h=state.overview?.settings?.hysteresis??10;
    const minimum=Math.max(20,h+1), gap=Math.max(21,2*h+1);
    values.hide=Math.max(minimum+gap,values.hide);
    values.lod1=Math.max(minimum,Math.min(values.lod1,values.hide-gap));
    return values;
  }
  function normalizePartFields(section, raw) {
    const values=normalizePartEdit(raw);
    const changed=Object.keys(values).some(name=>values[name]!==Number(raw[name]));
    if(changed)for(const name of Object.keys(values)) {
      section.querySelector(`[data-part-distance="${name}"]`).value=String(values[name]);
    }
    return {values,changed};
  }
  function partStatus(key, kind, message) {
    state.partMessages.set(key,{kind,message});
  }
  async function savePartDistances(slug, part, section) {
    if(state.busy || !state.overview)return;
    const key=partKey(slug,part);
    const previous=partRecord(state.overview,slug,part);
    const raw=readPartFields(section);
    state.partEdits.set(key,raw);
    if(!previous || !Number.isSafeInteger(previous.revision)) {
      partStatus(key,'error','Нет данных о ревизии. Нажми Refresh.');render();return;
    }
    let values;
    try {
      ({values}=normalizePartFields(section,raw));
      state.partEdits.set(key,Object.fromEntries(Object.entries(values).map(([name,value])=>[name,String(value)])));
    }catch(error){
      partStatus(key,'error',error.message);render();return;
    }
    const revision=previous.revision;
    state.busy=true;
    partStatus(key,'pending','Сохраняем…');render();
    // The persisted revision, not a successful HTTP status or an optimistic
    // local value, is the acknowledgement of a successful write.
    const matches = row => row?.lod1===values.lod1 && row?.hide===values.hide &&
      Number.isSafeInteger(row.revision) && row.revision===revision+1;
    try {
      const result=await request(`/api/real-estate/${encodeURIComponent(slug)}/parts/${encodeURIComponent(part)}/distances`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({distances:values,expectedRevision:revision})});
      state.preflight=null;
      $('lod-build-execute').hidden=true;
      $('lod-build-preview').hidden=true;
      const fresh=await request('/api/lod-manager',{cache:'no-store'});
      state.overview=fresh;
      const saved=partRecord(fresh,slug,part);
      if(!matches(result?.distances)||!matches(saved))
        throw Error('Сервер не подтвердил сохранённые значения. Проверь Refresh и повтори Save.');
      state.partEdits.delete(key);
      state.partMessages.delete(key);
      $('lod-house-message').textContent=`${slug}/${part}: сохранено. Studio Play обновится автоматически; для Runtime нужен новый Preflight.`;
    }catch(error){
      partStatus(key,'error',`Не подтверждено: ${error.message}`);
      $('lod-house-message').textContent=`${slug}/${part}: ${error.message}`;
    }finally{state.busy=false;render();}
  }
  const compact = value => Number(value || 0).toLocaleString('ru-RU');
  const date = value => value ? new Date(value*1000).toLocaleString('ru-RU') : '—';
  const indicators = {red:'Нет опубликованного LOD1',yellow:'LOD1 ✓ · LOD2 —',green:'LOD1 ✓ · LOD2 ✓'};
  const statuses = {NO_SNAPSHOT:['empty','Нет снимка'],CATALOG_CHANGED:['danger','Asset Registry изменился — нужен Scan'],
    SCANNED_THIS_SESSION:['ready','Scan выполнен в этой сессии'],NOT_LIVE_VERIFIED:['warning','Нужна повторная проверка Studio']};

  function render() {
    const data = state.overview;
    $('lod-scan').disabled = state.busy;
    $('lod-refresh').disabled = state.busy;
    $('lod-save-settings').disabled = state.busy;
    $('lod-enable-ready').disabled = state.busy;
    $('lod-disable-all').disabled = state.busy;
    $('lod-location-panel').hidden = state.domain !== 'location';
    $('lod-house-panel').hidden = state.domain !== 'house';
    $('lod-tab-location').setAttribute('aria-selected', String(state.domain === 'location'));
    $('lod-tab-house').setAttribute('aria-selected', String(state.domain === 'house'));
    $('lod-active-domain-title').textContent = state.domain === 'house' ? 'Real Estate' : 'Location Assets';
    if (!data) return;
    $('lod-tab-location').textContent = `Location Assets · ${data.items.length} видов`;
    $('lod-tab-house').textContent = `Real Estate · ${(data.realEstate?.items||[]).length} видов`;
    const snap = data.snapshot;
    const [style,label] = statuses[snap?.freshness || 'NO_SNAPSHOT'];
    $('lod-snapshot').innerHTML = `<div class="lm-snapshot-top"><span class="lm-chip lm-${style}">${escape(label)}</span>
      <strong>${snap ? `#${snap.revisionId} · ${date(snap.recordedUtc)}` : 'Первый Scan ещё не выполнен'}</strong></div>
      <div class="lm-meta">${snap ? `Place ID ${escape(snap.placeId)} · SHA256 ${escape(snap.fingerprint.slice(0,16))}…
        ${snap.verifiedUtc ? `· проверено ${date(snap.verifiedUtc)}` : ''}` : 'Открой Roblox Studio в Edit Mode и нажми Scan.'}</div>
      <p class="lm-note">${snap && !snap.catalogMatches ? 'Каталог публикаций изменён после снимка. Данные размещений могут быть устаревшими.' :
       'Даже при совпадении каталога изменения Workspace невозможно обнаружить без нового Scan. Снимок — не резервная копия .rbxl.'}</p>`;
    const metrics = [['Размещений',data.summary.placements],['Типов на Place',data.summary.typesWithPlacements],
      ['Зарегистрировано',data.summary.registeredTypes],['LOD1 опубликован',data.summary.lod1Types],
      ['Без Placement ID',data.summary.missingId],['Дубликатов ID',data.summary.duplicateId],
      ['Неоднозначных',data.summary.ambiguous],['Защищено · другие системы',data.summary.protectedExternal || 0],
      ['Проблем коллизий',data.summary.collisionReview]];
    $('lod-metrics').innerHTML = metrics.map(([label,value]) =>
      `<div class="lm-metric"><b>${compact(value)}</b><span>${escape(label)}</span></div>`).join('');
    const rows = data.items.filter(item => (state.filter === 'all' || item.indicator === state.filter)
      && (!state.term || item.slug.toLowerCase().includes(state.term)))
      .sort((a,b) => b.count-a.count || a.slug.localeCompare(b.slug));
    $('lod-rows').innerHTML = rows.length ? rows.map(item => {
      const flags = Object.entries(item.issues || {}).filter(([,count])=>count>0)
        .map(([key,count]) => `${({missingId:'Нет ID',duplicateId:'Повтор ID',ambiguous:'Неоднозначно',noModel:'Нет Model',collisionReview:'Collision',truncated:'Иерархия обрезана'})[key]}: ${count}`);
      const lod1 = item.lod1Status === 'PUBLISHED' ? `LOD1 · ${escape(item.lod1ModelId)}` : `LOD1 · ${escape(item.lod1Status)}`;
      const draft=state.assetEdits.get(item.slug)||{...item.distances,mode:item.streamingMode};
      const canEdit=Boolean(item.distances);
      return `<tr><td><strong class="lm-slug">${escape(item.slug)}</strong><small>${escape(item.category||'Location Asset')}${!item.recognizedByCatalog ? ' · нет в актуальном опубликованном каталоге':''}</small></td>
        <td class="lm-count">${compact(item.count)} <small>pcs</small>${item.protectedCount ? `<small class="lm-protected-count">+${compact(item.protectedCount)} Painter/other (${compact(item.runtimePainterCount||0)} ready)</small>` : ''}</td>
        <td><span class="lm-dot lm-${item.indicator}" title="${escape(indicators[item.indicator])}"></span>
          <span class="lm-quality">${escape(indicators[item.indicator])}</span><small>${lod1}</small></td>
        <td>${flags.length ? `<span class="lm-flag">${flags.map(escape).join(' · ')}</span>` : '<span class="lm-ok">—</span>'}
          ${item.protectedOwners?.length ? `<details class="lm-problems lm-external"><summary>Защищённые объекты (${item.protectedCount})</summary>
            ${item.protectedOwners.map(p => `<div class="lm-problem"><code>${escape(p.path)}</code>
              <small>${escape(p.kind === 'landscape_attachment' ? 'LandscapePainter · Managed Attachment' :
                p.kind === 'landscape_structure' ? 'LandscapePainter · Structure' : 'Unmanaged · Package')}${p.review ? ' · требуется проверка' : ''}</small>
              ${p.reason ? `<small>${escape(p.reason)}</small>` : ''}</div>`).join('')}
            </details>` : ''}
          ${item.problemPlacements?.length ? `<details class="lm-problems"><summary>Показать объекты (${item.problemPlacements.length})</summary>
            ${item.problemPlacements.map(p => `<div class="lm-problem"><code>${escape(p.path)}</code>
              <small>${escape(p.issues?.join(' · ') || (p.placementId ? 'Placement ID: ' + p.placementId : 'Нет Placement ID'))}</small></div>`).join('')}
            </details>` : ''}</td>
        <td><select class="lm-stream-mode" data-stream-slug="${escape(item.slug)}"
          aria-label="Streaming mode ${escape(item.slug)}" ${state.busy || !canEdit ? 'disabled' : ''}>
          ${[['auto','Auto · FULL → Hide'],['off','Off · Workspace'],['full','FULL → Hide'],['lod1','FULL / LOD1'],['lod2','FULL / LOD1 / LOD2']]
            .map(([mode,label])=>`<option value="${mode}" ${draft.mode===mode?'selected':''}
              ${(mode!=='off' && mode!=='auto' && !item.streamingEligible) || (mode==='lod1' && item.lod1Status!=='PUBLISHED') || (mode==='lod2' && item.lod2Status!=='PUBLISHED')?'disabled':''}>${label}</option>`).join('')}
          </select><div class="lm-stream-status">${escape(item.streamingReason || (item.streamingMode==='auto' ? 'По умолчанию FULL; все размещения данного типа' : 'Выбор сохранён'))}</div></td></tr>${canEdit?`<tr class="lm-asset-distance-row"><td colspan="5"><div class="lm-asset-distances" data-asset-distance-slug="${escape(item.slug)}">
          ${[['lod1','LOD1'],['lod2','LOD2'],['hide','UNLOADED']].map(([key,label])=>`<label>${label} · studs<input type="number" min="1" max="10000" step="1" data-asset-distance="${key}" value="${escape(draft[key])}" ${state.busy?'disabled':''}></label>`).join('')}
          <button type="button" data-asset-distance-save="${escape(item.slug)}" ${state.busy?'disabled':''}>Сохранить</button>
          <small class="lm-asset-feedback" role="status">${escape(state.assetMessages.get(item.slug)||'Индивидуальный профиль')}</small></div></td></tr>`:''}`;
    }).join('') : '<tr><td colspan="5" class="lm-empty">Нет записей с такими условиями.</td></tr>';
    const houses=data.realEstate?.items || [];
    const visibleHouses=houses.filter(h=>{
      const parts=h.parts||[];
      const matchesText=!state.houseTerm || h.slug.toLowerCase().includes(state.houseTerm) ||
        parts.some(p=>p.name.toLowerCase().includes(state.houseTerm));
      if(!matchesText)return false;
      if(state.houseFilter==='ready')return Boolean(h.ready);
      if(state.houseFilter==='review')return !h.ready;
      return true;
    });
    $('lod-house-count').textContent = `${visibleHouses.length} / ${houses.length} домов · ${data.realEstate?.placements||0} Plot bindings`;
    $('lod-house-rows').innerHTML=visibleHouses.length ? visibleHouses.map(h=>{
      const parts=h.parts||[];
      const ready=parts.filter(p=>h.partLod1?.[p.name]?.status==='PUBLISHED').length;
      const mode=h.mode||'off';
      const groups=groupHouseParts(parts).map(group=>{
        const groupKey=h.slug+'/'+group.key;
        const cards=group.parts.map(part=>{
          const lod=h.partLod1?.[part.name]||{};
          const distances=h.partStreaming?.[part.name];
          const key=partKey(h.slug,part.name);
          const fields=state.partEdits.get(key)||distances||{};
          const status=state.partMessages.get(key)||{kind:distances?'saved':'error',message:distances?
            `Сохранено: ${distances.lod1} / ${distances.hide} studs · rev ${distances.revision}`:
            'Нет данных о дистанциях. Нажми Refresh.'};
          const disabled=state.busy||!distances;
          const published=lod.status==='PUBLISHED';
          const sequence=mode==='lod1'&&published?'FULL → LOD1 → UNLOADED':'FULL → UNLOADED';
          return `<article class="lm-house-part" aria-label="${escape(part.name)}" data-part-house="${escape(h.slug)}" data-part-name="${escape(part.name)}">
            <div class="lm-part-top"><div class="lm-part-name"><strong>${escape(part.name)}</strong>
              <small>${escape(part.appearance||'material')} · ${escape(part.color||'—')}</small></div>
              <span class="lm-part-state ${published?'is-published':'is-missing'}" title="${escape(lod.status||'NOT_REGISTERED')}">
                ${published?'LOD1 опубликован':'Без опубликованного LOD1'}</span></div>
            <p class="lm-part-path">${sequence}</p>
            <div class="lm-house-profile-fields" data-part-distance-panel="${escape(part.name)}">
              <label>LOD1 от · studs<input type="number" min="20" max="10000" step="1" data-part-distance="lod1"
                value="${escape(fields.lod1)}" ${disabled?'disabled':''}></label>
              <label>UNLOADED от · studs<input type="number" min="1" max="10000" step="1" data-part-distance="hide"
                value="${escape(fields.hide)}" ${disabled?'disabled':''}></label>
              <button type="button" class="lm-part-save" data-part-distance-save="${escape(part.name)}"
                data-part-house="${escape(h.slug)}" ${disabled?'disabled':''}>Сохранить</button>
            </div>
            <p class="lm-part-feedback ${escape(status.kind)}" role="status" aria-live="polite">${escape(status.message)}</p>
            <div class="lm-part-footer"><small>Model ID: ${escape(lod.modelAssetId||'—')}</small>
              <button type="button" class="lm-part-manage" data-house-lod-edit="${escape(h.slug)}"
                data-house-lod-part="${escape(part.name)}">LOD1 FBX · Real Estate</button></div>
          </article>`;
        }).join('');
        return `<details class="lm-part-group" data-house-group="${escape(groupKey)}"
          ${state.collapsedGroups.has(groupKey)?'':'open'}>
          <summary><span>${escape(group.label)}</span><small>${group.parts.length} частей</small></summary>
          <div class="lm-part-grid">${cards}</div></details>`;
      }).join('');
      const readyText=h.ready?'Готов к Preflight':(h.warnings||[]).join(' · ')||'Требуется проверка';
      return `<details class="lm-house-card" data-house-details="${escape(h.slug)}" ${state.expandedHouses.has(h.slug)?'open':''}>
        <summary><span class="lm-house-title"><strong>${escape(h.slug)}</strong><small>${compact(h.count)} размещений</small></span>
          <span class="lm-house-summary-meta">${ready}/${parts.length} LOD1</span>
          <span class="lm-house-readiness ${h.ready?'is-ready':'is-review'}">${h.ready?'Готов':'Проверить'}</span></summary>
        <div class="lm-house-content">
          <div class="lm-house-settings"><label>Режим House Streaming
            <select class="lm-house-stream-mode" data-house-slug="${escape(h.slug)}"
              aria-label="House streaming mode ${escape(h.slug)}" ${state.busy?'disabled':''}>
              ${[['off','Off · Workspace'],['full','FULL → UNLOADED'],['lod1','FULL → LOD1 → UNLOADED']]
                .map(([value,label])=>`<option value="${value}" ${mode===value?'selected':''}
                  ${(value!=='off'&&mode!==value&&h.fullStatus!=='PUBLISHED')||
                    (value==='lod1'&&mode!=='lod1'&&ready===0)?'disabled':''}>${label}</option>`).join('')}
            </select></label>
            <span class="lm-house-readiness-text ${h.ready?'is-ready':'is-review'}">${escape(readyText)}</span>
          </div>
          <div class="lm-house-groups">${groups||'<p class="lm-note">Нет визуальных частей</p>'}</div>
        </div>
      </details>`;
    }).join('') : `<p class="lm-house-empty">${houses.length?'Нет домов по выбранному фильтру.':'Нет зарегистрированных домов.'}</p>`;
    $('lod-count').textContent = `${rows.length} / ${data.items.length} видов`;
    $('lod-revisions').innerHTML = data.revisions.length ? data.revisions.map(r =>
      `<span class="lm-revision">#${r.id} · ${date(r.recordedUtc)} · ${compact(r.total)} pcs
      <a href="/api/location-place-registry/revisions/${r.id}" target="_blank" rel="noopener noreferrer" title="Полный снимок JSON">JSON</a></span>`).join('') : '<span class="lm-note">История снимков пуста.</span>';
    $('lod-source-path').textContent = data.build?.sourceFile || 'place/game1_runtime_source.rbxlx';
    $('lod-prepare').disabled = state.busy || !data.build?.canPreflight;
    if (!data.build?.canPreflight) {
      state.preflight = null;
      $('lod-build-preview').hidden = true;
      $('lod-build-execute').hidden = true;
      $('lod-build-execute').disabled = true;
      $('lod-build-status').textContent = 'Сначала Scan Place в текущей сессии. Затем сохрани XML Place и запусти Preflight.';
    }
    $('lod-warnings').textContent = snap?.warnings?.length ? snap.warnings.join(' · ') :
      (data.summary.scanWarnings ? `Предупреждений: ${data.summary.scanWarnings}` : '');
  }

  async function load() {
    if(state.busy)return;
    state.busy=true;render();
    try {
      state.overview = await request('/api/lod-manager',{cache:'no-store'});
      fillSettings(state.overview.settings);
      render();
      $('lod-status').textContent = 'Показан последний сохранённый снимок. Для проверки изменений в Studio нажми Scan.';
    } catch(error) { $('lod-status').textContent = `LOD Manager: ${error.message}`; }
    finally {state.busy=false;render();}
  }
  async function scan() {
    if(state.busy)return;
    state.busy = true;
    $('lod-scan').disabled = true;
    $('lod-status').textContent = 'Studio Edit Mode · идёт Scan через существующий Place Registry…';
    try {
      const response = await request('/api/lod-manager/scan', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      state.preflight = null;
      state.overview = response.overview;
      render();
      $('lod-status').textContent = `Снимок #${response.scan.revisionId}: ${response.scan.unchanged?'размещения без изменений':'ревизия сохранена'}.`+
        (response.scan.incomplete ? ' Есть предупреждения — смотри ниже.' : '');
    } catch(error) {
      $('lod-status').textContent = `Scan не выполнен: ${error.message}. Проверь Studio Edit Mode, HTTP Requests и Game1Bridge.`;
    } finally {state.busy=false;render();}
  }

  async function preflight() {
    if(state.busy || !state.overview?.build?.canPreflight)return;
    state.busy = true;
    state.preflight = null;
    $('lod-prepare').disabled = true;
    $('lod-build-preview').hidden = true;
    $('lod-build-execute').hidden = true;
    $('lod-build-status').textContent = 'Проверяем сохранённый XML Place и каждый выбранный экземпляр…';
    try {
      const plan = await request('/api/lod-manager/preflight', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      state.preflight = plan;
      const untouchedHouses=Object.entries(plan.untouchedHouseCounts||{});
      const unselectedLocations=plan.untouchedLocations||[];
      const omitted=untouchedHouses.reduce((count,[,n])=>count+n,0);
      const exclusions=[
        ...untouchedHouses.map(([slug,n])=>`${slug}: ${n} домов остаются в Workspace`),
        ...unselectedLocations.map(item=>`${item.slug}: ${item.count} остаются в Workspace${item.eligible?'':' (структура не поддержана)'}`)
      ];
      $('lod-build-preview').textContent = `Snapshot #${plan.snapshotRevision} · Location: ${plan.eligible} MeshParts · Real Estate: ${plan.houseCount||0} домов / ${plan.houseMeshParts||0} MeshParts → technical Parts · ` +
        Object.entries(plan.counts || {}).map(([slug,count])=>`${slug}: ${count}`).join(' · ') +
        ` · зарегистрированные Plot-пивоты не требуют совпадения с домами Workspace` +
        ` · защищённых объектов не трогаем: ${plan.protectedNotModified}` +
        ` · Индивидуальные дистанции: ${Object.keys(plan.assetDistances||{}).length} типов` +
        ` · Workspace Target ${plan.workspace.targetRadius} studs · SHA256 исходника: ${plan.sourceSha256}` +
        (exclusions.length ? `\nНЕ ВКЛЮЧЕНЫ В RUNTIME STREAMING (${omitted} домов, ${unselectedLocations.reduce((n,x)=>n+x.count,0)} Location):\n${exclusions.join('\n')}` : '');
      $('lod-build-preview').hidden = false;
      $('lod-build-execute').hidden = false;
      $('lod-build-execute').disabled = false;
      $('lod-build-status').textContent = exclusions.length
        ? 'Preflight OK, НО часть объектов останется в Workspace — смотри список выше. Включи их streaming profile либо собери частичный Runtime Draft.'
        : 'Preflight OK. Build создаст проверенный backup и отдельную Runtime XML-копию; ничего не удалит в Studio.';
    } catch(error) {
      $('lod-build-status').textContent = `Preflight остановлен: ${error.message}`;
    } finally { state.busy = false; render(); }
  }
  async function prepare() {
    if(state.busy || !state.preflight)return;
    state.busy = true;
    const token = state.preflight.token;
    state.preflight = null;
    $('lod-build-execute').disabled = true;
    $('lod-prepare').disabled = true;
    $('lod-build-status').textContent = 'Создаём backup, проверяем SHA256, собираем отдельный Runtime Place…';
    try {
      const result = await request('/api/lod-manager/prepare', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({token})});
      const remaining=Object.entries(result.untouchedHouseCounts||{});
      $('lod-build-status').textContent = `Runtime draft создан: Location ${result.removedVisualMeshParts} MeshParts удалены · Real Estate ${result.housePlacements||0} домов / ${result.convertedHouseVisualMeshParts||0} MeshParts заменены прокси.` +
        (remaining.length ? ` ВНИМАНИЕ: ${remaining.map(([slug,n])=>`${slug} × ${n}`).join(', ')} остались FULL в Workspace.` : '') +
        ' Публикация ЗАБЛОКИРОВАНА до Studio / мобильной проверки.';
      $('lod-build-preview').textContent = `Backup: ${result.backupPath}
Runtime: ${result.runtimePath}
Placement manifest: ${result.manifestPath}
Build report: ${result.reportPath}`;
      $('lod-build-preview').hidden = false;
    } catch(error) { $('lod-build-status').textContent = `Runtime build остановлен: ${error.message}`; }
    finally {
      state.busy = false;
      $('lod-build-execute').hidden = true;
      render();
    }
  }
  for (const domain of ['location','house']) {
    $(`lod-tab-${domain}`).addEventListener('click', () => {state.domain=domain;render();});
  }
  $('lod-house-rows').addEventListener('toggle', event => {
    const detail=event.target;
    if(detail?.isConnected===false)return;
    if(detail?.dataset?.houseDetails){
      if(detail.open)state.expandedHouses.add(detail.dataset.houseDetails);
      else state.expandedHouses.delete(detail.dataset.houseDetails);
    }else if(detail?.dataset?.houseGroup){
      if(detail.open)state.collapsedGroups.delete(detail.dataset.houseGroup);
      else state.collapsedGroups.add(detail.dataset.houseGroup);
    }
  }, true);
  $('lod-house-rows').addEventListener('input', event => {
    const field=event.target;
    if(!field?.dataset?.partDistance)return;
    const section=field.closest('.lm-house-part');
    if(!section)return;
    const key=partKey(section.dataset.partHouse,section.dataset.partName);
    state.partEdits.set(key,readPartFields(section));
    partStatus(key,'pending','Не сохранено — нажми Сохранить.');
    const feedback=section.querySelector('.lm-part-feedback');
    if(feedback){feedback.className='lm-part-feedback pending';feedback.textContent=state.partMessages.get(key).message;}
  });
  $('lod-house-rows').addEventListener('click', event => {
    const distanceButton=event.target.closest?.('button[data-part-distance-save]');
    if(distanceButton){
      const section=distanceButton.closest('.lm-house-part');
      if(section)return savePartDistances(distanceButton.dataset.partHouse,distanceButton.dataset.partDistanceSave,section);
      return;
    }
    const edit=event.target.closest?.('button[data-house-lod-edit]');
    if(edit){
      if(typeof window.game1RealEstateOpenLod1==='function')
        window.game1RealEstateOpenLod1(edit.dataset.houseLodEdit,edit.dataset.houseLodPart);
      else $('nav-real-estate').click();
    }
  });
  $('lod-house-rows').addEventListener('change', event => {
    const field=event.target;
    if(field?.dataset?.partDistance){
      const section=field.closest('.lm-house-part');
      if(!section)return;
      const key=partKey(section.dataset.partHouse,section.dataset.partName);
      const raw=readPartFields(section);
      try {
        const {values,changed}=normalizePartFields(section,raw);
        if(changed){
          state.partEdits.set(key,Object.fromEntries(Object.entries(values).map(([name,value])=>[name,String(value)])));
          partStatus(key,'pending',`Скорректировано: ${values.lod1} / ${values.hide} studs. Нажми Сохранить.`);
          const feedback=section.querySelector('.lm-part-feedback');
          if(feedback){feedback.className='lm-part-feedback pending';feedback.textContent=state.partMessages.get(key).message;}
        }
      }catch(error){/* Keep unfinished input; Save reports validation errors. */}
      return;
    }
    const el=event.target, slug=el?.dataset?.houseSlug;
    if(slug)saveHouseMode(slug,el.value);
  });
  $('lod-house-search').addEventListener('input',event=>{
    state.houseTerm=event.target.value.trim().toLowerCase();render();
  });
  $('lod-house-filter').addEventListener('change',event=>{
    state.houseFilter=event.target.value;render();
  });
  function assetDraft(slug) {
    const item=state.overview?.items.find(row=>row.slug===slug);
    return state.assetEdits.get(slug)||{...item?.distances,mode:item?.streamingMode};
  }
  function normalizeAssetDraft(draft) {
    const d={};
    for(const key of ['lod1','lod2','hide']){
      const n=Number(draft[key]);
      if(!String(draft[key]??'').trim()||!Number.isSafeInteger(n)||n<1||n>10000)
        throw Error('Дистанции: целые числа от 1 до 10000 studs');
      d[key]=n;
    }
    const h=state.overview.settings.hysteresis, min=Math.max(16,h+1), gap=2*h+1;
    const active=draft.mode==='lod2'?['lod1','lod2']:draft.mode==='lod1'?['lod1']:[];
    d.hide=Math.max(d.hide,min+gap*active.length);
    let ceiling=d.hide;
    for(let i=active.length-1;i>=0;i--){const key=active[i];d[key]=Math.max(min+i*gap,Math.min(d[key],ceiling-gap));ceiling=d[key];}
    return d;
  }
  $('lod-rows').addEventListener('input', event => {
    const el=event.target, key=el?.dataset?.assetDistance;
    const slug=el?.closest?.('[data-asset-distance-slug]')?.dataset?.assetDistanceSlug;
    if(key&&slug){state.assetEdits.set(slug,{...assetDraft(slug),[key]:el.value});state.assetMessages.set(slug,'Не сохранено');const feedback=el.closest('[data-asset-distance-slug]').querySelector('.lm-asset-feedback');if(feedback)feedback.textContent='Не сохранено';}
  });
  $('lod-rows').addEventListener('change', event => {
    const el=event.target, slug=el?.dataset?.streamSlug;
    if(slug){state.assetEdits.set(slug,{...assetDraft(slug),mode:el.value});state.assetMessages.set(slug,'Не сохранено');render();}
    const panel=el?.closest?.('[data-asset-distance-slug]');
    if(panel&&el.dataset.assetDistance){
      const id=panel.dataset.assetDistanceSlug;
      try{const draft=assetDraft(id), values=normalizeAssetDraft(draft);state.assetEdits.set(id,{...values,mode:draft.mode});for(const key of Object.keys(values))panel.querySelector(`[data-asset-distance="${key}"]`).value=String(values[key]);const feedback=panel.querySelector('.lm-asset-feedback');if(feedback)feedback.textContent='Не сохранено';}catch(error){/* Save reports invalid input. */}
    }
  });
  $('lod-rows').addEventListener('click', async event => {
    const button=event.target.closest?.('[data-asset-distance-save]'),slug=button?.dataset.assetDistanceSave;
    if(!slug||state.busy)return;
    try{
      const draft=assetDraft(slug), distances=normalizeAssetDraft(draft);
      const ok=await saveSettings({modes:{[slug]:draft.mode},assetDistances:{[slug]:distances}});
      if(ok){state.assetEdits.delete(slug);state.assetMessages.set(slug,'Сохранено · Studio Play Sync');}
      else state.assetMessages.set(slug,$('lod-settings-status').textContent);
    }catch(error){state.assetMessages.set(slug,error.message);}
    render();
  });
  $('lod-enable-ready').addEventListener('click', () => {
    if(!state.overview || state.busy)return;
    const modes={};
    for(const item of state.overview.items)if(item.streamingEligible)
      modes[item.slug]=item.lod2Status==='PUBLISHED'?'lod2':item.lod1Status==='PUBLISHED'?'lod1':'full';
    if(Object.keys(modes).length)saveSettings({modes});
    else $('lod-settings-status').textContent='Нет готовых ассетов; сначала проверь Collision Blueprint и Scan.';
  });
  $('lod-disable-all').addEventListener('click', () => {
    if(!state.overview || state.busy)return;
    const modes={};
    for(const item of state.overview.items)modes[item.slug]='off';
    saveSettings({modes});
  });
  $('lod-preset-default').addEventListener('click', () => {
    fillSettings(defaultSettings);
    $('lod-settings-status').textContent='Пресет заполнен. Нажми Save settings для сохранения.';
  });
  $('lod-save-settings').addEventListener('click', () => {
    try{saveSettings(readSettings())}catch(error){$('lod-settings-status').textContent=error.message}
  });
  $('lod-copy-workspace').addEventListener('click', async () => {
    try {
      const w=readSettings().workspace;
      const command=`-- Eyesland LOD Manager · Roblox Studio Command Bar · EDIT mode.\n`+
        `local ws = game:GetService("Workspace")\n`+
        `local settings = {StreamingEnabled=${w.streamingEnabled}, StreamingMinRadius=${w.minRadius}, `+
        `StreamingTargetRadius=${w.targetRadius}, `+
        `ModelStreamingBehavior=Enum.ModelStreamingBehavior.${w.modelStreamingBehavior}, `+
        `StreamingIntegrityMode=Enum.StreamingIntegrityMode.${w.streamingIntegrityMode}, `+
        `StreamOutBehavior=Enum.StreamOutBehavior.${w.streamOutBehavior}}\n`+
        `for key, value in pairs(settings) do\n`+
        `  local ok, err = pcall(function() ws[key] = value end)\n`+
        `  if not ok then warn(key .. ": " .. tostring(err) .. " · set manually in Workspace Properties") end\n`+
        `end\nprint("Workspace streaming profile applied; save Place to persist")`;
      await navigator.clipboard.writeText(command);
      $('lod-settings-status').textContent='Команда скопирована. Запусти в Studio Edit Mode; если свойство защищено, установи его в Workspace Properties.';
    }catch(error){$('lod-settings-status').textContent=`Copy failed: ${error.message}`}
  });
  $('lod-settings-section').addEventListener('click',event=>{
    const target=event.target;
    if(target?.classList?.contains('lm-help'))$('lod-settings-status').textContent=target.title;
  });
  $('lod-settings-section').addEventListener('keydown',event=>{
    if((event.key==='Enter'||event.key===' ') && event.target?.classList?.contains('lm-help')){
      $('lod-settings-status').textContent=event.target.title;
    }
  });
  for(const id of helpIds){$(id).addEventListener('input',()=>{$('lod-settings-status').textContent='Настройки изменены. Нажми Save settings.';});}
  $('lod-prepare').addEventListener('click', preflight);
  $('lod-build-execute').addEventListener('click', prepare);
  $('lod-scan').addEventListener('click',scan);
  $('lod-refresh').addEventListener('click',load);
  $('lod-search').addEventListener('input',event=>{state.term=event.target.value.trim().toLowerCase();render();});
  $('lod-filter').addEventListener('change',event=>{state.filter=event.target.value;render();});
  window.game1LodManagerLoad = load;
})();
