/* LOD Manager: authoritative Place Registry inventory + project-owned streaming policy. */
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = {overview:null, busy:false, filter:'all', term:'', preflight:null};
  const defaultSettings = {
    distances:{lod1:120,lod2:260,hide:400,hysteresis:12},
    workspace:{streamingEnabled:true,minRadius:64,targetRadius:1024,
      modelStreamingBehavior:'Improved',streamingIntegrityMode:'PauseOutsideLoadedArea',streamOutBehavior:'Opportunistic'}
  };
  const helpIds = ['lod-distance-1','lod-distance-2','lod-distance-hide','lod-distance-hysteresis',
    'lod-workspace-enabled','lod-workspace-min-radius','lod-workspace-target-radius',
    'lod-workspace-model','lod-workspace-integrity','lod-workspace-streamout'];
  function fillSettings(settings) {
    const d=settings.distances,w=settings.workspace;
    $('lod-distance-1').value=String(d.lod1); $('lod-distance-2').value=String(d.lod2);
    $('lod-distance-hide').value=String(d.hide); $('lod-distance-hysteresis').value=String(d.hysteresis);
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
    const d={lod1:integer('lod-distance-1'),lod2:integer('lod-distance-2'),
      hide:integer('lod-distance-hide'),hysteresis:integer('lod-distance-hysteresis')};
    if(!(d.lod1>=16 && d.lod1<d.lod2 && d.lod2<d.hide && d.hide<=10000 &&
         d.hysteresis>=0 && d.hysteresis<=100 && d.lod1>d.hysteresis &&
         d.lod2-d.lod1>2*d.hysteresis && d.hide-d.lod2>2*d.hysteresis))
      throw Error('LOD1 < LOD2 < Hide и между порогами нужен запас для гистерезиса');
    const w={streamingEnabled:$('lod-workspace-enabled').checked,
      minRadius:integer('lod-workspace-min-radius'),targetRadius:integer('lod-workspace-target-radius'),
      modelStreamingBehavior:$('lod-workspace-model').value,
      streamingIntegrityMode:$('lod-workspace-integrity').value,streamOutBehavior:$('lod-workspace-streamout').value};
    if(w.minRadius<32 || w.minRadius>512 || w.targetRadius<96 || w.targetRadius>4096 || w.targetRadius<=w.minRadius)
      throw Error('Workspace: Min 32–512, Target 96–4096 и Target > Min');
    return {distances:d,workspace:w};
  }
  async function saveSettings(payload) {
    if (state.busy) return;
    state.busy=true;
    $('lod-settings-status').textContent='Сохраняем настройки проекта…';
    try {
      const view=await request('/api/lod-manager/settings', {method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      state.overview=view; state.preflight=null;
      $('lod-build-confirm-label').hidden=true; $('lod-build-execute').hidden=true;
      $('lod-build-preview').hidden=true;
      $('lod-build-status').textContent='Настройки изменены. Запусти Preflight по новому профилю.';
      $('lod-settings-status').textContent='Сохранено. Preflight нужно выполнить заново; Studio не изменена.';
      fillSettings(view.settings);
    } catch(error) {
      $('lod-settings-status').textContent=`Не сохранено: ${error.message}`;
    } finally {state.busy=false;render();}
  }

  async function saveHouseMode(slug, mode) {
    if(state.busy || !state.overview)return;
    const house=(state.overview.realEstate?.items||[]).find(h=>h.slug===slug);
    if(!house || !house.profile)return;
    const old=house.profile;
    const values={mode,lod1:old.lod1,hide:old.hide,hysteresis:old.hysteresis};
    state.busy=true;
    $('lod-settings-status').textContent=`${slug}: сохраняем Runtime Profile…`;
    try {
      await request(`/api/real-estate/${encodeURIComponent(slug)}/runtime-profile`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({profile:values,expectedRevision:old.revision})});
      state.overview=await request('/api/lod-manager');
      state.preflight=null;
      $('lod-build-preview').hidden=true;
      $('lod-build-confirm-label').hidden=true;
      $('lod-build-execute').hidden=true;
      $('lod-build-status').textContent='Профиль дома изменён — нужен новый Preflight и Runtime Draft.';
      $('lod-settings-status').textContent=`${slug}: ${mode} сохранён через Real Estate.`;
    } catch(error) {
      $('lod-settings-status').textContent=`${slug}: ${error.message}`;
    } finally {state.busy=false;render();}
  }

  const compact = value => Number(value || 0).toLocaleString('ru-RU');
  const date = value => value ? new Date(value*1000).toLocaleString('ru-RU') : '—';
  const indicators = {red:'Нет опубликованного LOD1',yellow:'LOD1 ✓ · LOD2 —',green:'LOD1 ✓ · LOD2 ✓'};
  const statuses = {NO_SNAPSHOT:['empty','Нет снимка'],CATALOG_CHANGED:['danger','Asset Registry изменился — нужен Scan'],
    SCANNED_THIS_SESSION:['ready','Scan выполнен в этой сессии'],NOT_LIVE_VERIFIED:['warning','Нужна повторная проверка Studio']};

  function render() {
    const data = state.overview;
    $('lod-scan').disabled = state.busy;
    $('lod-save-settings').disabled = state.busy;
    $('lod-enable-ready').disabled = state.busy;
    $('lod-disable-all').disabled = state.busy;
    if (!data) return;
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
          aria-label="Streaming mode ${escape(item.slug)}" ${state.busy ? 'disabled' : ''}>
          ${[['auto','Auto · FULL → Hide'],['off','Off · Workspace'],['full','FULL → Hide'],['lod1','FULL / LOD1'],['lod2','FULL / LOD1 / LOD2']]
            .map(([mode,label])=>`<option value="${mode}" ${item.streamingMode===mode?'selected':''}
              ${(mode!=='off' && mode!=='auto' && !item.streamingEligible) || (mode==='lod1' && item.lod1Status!=='PUBLISHED') || (mode==='lod2' && item.lod2Status!=='PUBLISHED')?'disabled':''}>${label}</option>`).join('')}
          </select><div class="lm-stream-status">${escape(item.streamingReason || (item.streamingMode==='auto' ? 'По умолчанию FULL; все размещения данного типа' : 'Выбор сохранён'))}</div></td></tr>`;
    }).join('') : '<tr><td colspan="5" class="lm-empty">Нет записей с такими условиями.</td></tr>';
    const houses=data.realEstate?.items || [];
    $('lod-house-count').textContent = `${data.realEstate?.selected||0} профилей · ${data.realEstate?.placements||0} зарегистрированных точек (не домов в Workspace)`;
    $('lod-house-rows').innerHTML=houses.length ? houses.map(h => `<tr>
      <td><strong>${escape(h.slug)}</strong></td><td>${compact(h.count)}</td>
      <td><select class="lm-house-stream-mode" data-house-slug="${escape(h.slug)}"
        aria-label="House streaming mode ${escape(h.slug)}" ${state.busy?'disabled':''}>
        ${[['off','Off · Workspace'],['full','FULL → Unloaded'],['lod1','FULL → House LOD1 → Unloaded']]
          .map(([mode,label])=>`<option value="${mode}" ${h.mode===mode?'selected':''}
            ${(mode!=='off' && h.mode!==mode && (h.fullStatus!=='PUBLISHED')) ||
              (mode==='lod1' && h.mode!=='lod1' && h.lod1Status!=='PUBLISHED')?'disabled':''}>${label}</option>`).join('')}
        </select></td>
      <td>${escape(h.lod1Status)}</td>
      <td>${h.mode==='off' ? '<span class="lm-note">Не выбран</span>' :
         h.ready ? '<span class="lm-ready">Профиль готов · XML-дома необязательны</span>' :
         `<span class="lm-danger">${escape((h.warnings||[]).join(' · ')||'Проверь публикацию')}</span>`}</td></tr>`).join('') :
      '<tr><td colspan="5">Нет зарегистрированных домов</td></tr>';
    $('lod-count').textContent = `${rows.length} / ${data.items.length} видов`;
    $('lod-revisions').innerHTML = data.revisions.length ? data.revisions.map(r =>
      `<span class="lm-revision">#${r.id} · ${date(r.recordedUtc)} · ${compact(r.total)} pcs
      <a href="/api/location-place-registry/revisions/${r.id}" target="_blank" rel="noopener noreferrer" title="Полный снимок JSON">JSON</a></span>`).join('') : '<span class="lm-note">История снимков пуста.</span>';
    $('lod-source-path').textContent = data.build?.sourceFile || 'place/game1_runtime_source.rbxlx';
    $('lod-prepare').disabled = state.busy || !data.build?.canPreflight;
    if (!data.build?.canPreflight) {
      state.preflight = null;
      $('lod-build-preview').hidden = true;
      $('lod-build-confirm-label').hidden = true;
      $('lod-build-execute').hidden = true;
      $('lod-build-execute').disabled = true;
      $('lod-build-status').textContent = 'Сначала Scan Place в текущей сессии. Затем сохрани XML Place и запусти Preflight.';
    }
    $('lod-warnings').textContent = snap?.warnings?.length ? snap.warnings.join(' · ') :
      (data.summary.scanWarnings ? `Предупреждений: ${data.summary.scanWarnings}` : '');
  }

  async function load() {
    try {
      state.overview = await request('/api/lod-manager');
      fillSettings(state.overview.settings);
      render();
      $('lod-status').textContent = 'Показан последний сохранённый снимок. Для проверки изменений в Studio нажми Scan.';
    } catch(error) { $('lod-status').textContent = `LOD Manager: ${error.message}`; }
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
    $('lod-build-confirm-label').hidden = true;
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
        ` · LOD1 ${plan.distances.lod1} / LOD2 ${plan.distances.lod2} / Hide ${plan.distances.hide} studs` +
        ` · Workspace Target ${plan.workspace.targetRadius} studs · SHA256 исходника: ${plan.sourceSha256}` +
        (exclusions.length ? `\nНЕ ВКЛЮЧЕНЫ В RUNTIME STREAMING (${omitted} домов, ${unselectedLocations.reduce((n,x)=>n+x.count,0)} Location):\n${exclusions.join('\n')}` : '');
      $('lod-build-preview').hidden = false;
      $('lod-build-confirm').value = '';
      $('lod-build-confirm-label').hidden = false;
      $('lod-build-execute').hidden = false;
      $('lod-build-execute').disabled = true;
      $('lod-build-status').textContent = exclusions.length
        ? 'Preflight OK, НО часть объектов останется в Workspace — смотри список выше. Включи их streaming profile или подтверди частичную сборку.'
        : 'Preflight OK. Build создаст проверенный backup и отдельную Runtime XML-копию; ничего не удалит в Studio. Введи подтверждение.';
    } catch(error) {
      $('lod-build-status').textContent = `Preflight остановлен: ${error.message}`;
    } finally { state.busy = false; render(); }
  }
  async function prepare() {
    if(state.busy || !state.preflight || $('lod-build-confirm').value !== 'PREPARE RUNTIME')return;
    state.busy = true;
    const token = state.preflight.token;
    state.preflight = null;
    $('lod-build-execute').disabled = true;
    $('lod-prepare').disabled = true;
    $('lod-build-status').textContent = 'Создаём backup, проверяем SHA256, собираем отдельный Runtime Place…';
    try {
      const result = await request('/api/lod-manager/prepare', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({token,confirmation:'PREPARE RUNTIME'})});
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
      $('lod-build-confirm-label').hidden = true;
      $('lod-build-execute').hidden = true;
      render();
    }
  }
  $('lod-house-rows').addEventListener('change', event => {
    const el=event.target, slug=el?.dataset?.houseSlug;
    if(slug)saveHouseMode(slug,el.value);
  });
  $('lod-rows').addEventListener('change', event => {
    const el=event.target, slug=el?.dataset?.streamSlug;
    if(!slug || !state.overview)return;
    saveSettings({modes:{[slug]:el.value}});
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
  $('lod-build-confirm').addEventListener('input', event => {
    $('lod-build-execute').disabled = state.busy || !state.preflight || event.target.value !== 'PREPARE RUNTIME';
  });
  $('lod-scan').addEventListener('click',scan);
  $('lod-refresh').addEventListener('click',load);
  $('lod-search').addEventListener('input',event=>{state.term=event.target.value.trim().toLowerCase();render();});
  $('lod-filter').addEventListener('change',event=>{state.filter=event.target.value;render();});
  window.game1LodManagerLoad = load;
})();
