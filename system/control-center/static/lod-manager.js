/* Location Assets LOD Manager: read-only inventory over Place Registry snapshots. */
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = {overview:null, busy:false, filter:'all', term:'', preflight:null};
  const compact = value => Number(value || 0).toLocaleString('ru-RU');
  const date = value => value ? new Date(value*1000).toLocaleString('ru-RU') : '—';
  const indicators = {red:'Нет опубликованного LOD1',yellow:'LOD1 ✓ · LOD2 —',green:'LOD1 ✓ · LOD2 ✓'};
  const statuses = {NO_SNAPSHOT:['empty','Нет снимка'],CATALOG_CHANGED:['danger','Asset Registry изменился — нужен Scan'],
    SCANNED_THIS_SESSION:['ready','Scan выполнен в этой сессии'],NOT_LIVE_VERIFIED:['warning','Нужна повторная проверка Studio']};

  function render() {
    const data = state.overview;
    $('lod-scan').disabled = state.busy;
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
        <td class="lm-count">${compact(item.count)} <small>pcs</small>${item.protectedCount ? `<small class="lm-protected-count">+${compact(item.protectedCount)} protected</small>` : ''}</td>
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
            </details>` : ''}</td></tr>`;
    }).join('') : '<tr><td colspan="4" class="lm-empty">Нет записей с такими условиями.</td></tr>';
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
      $('lod-build-preview').textContent = `Snapshot #${plan.snapshotRevision} · ${plan.eligible} визуальных MeshParts к удалению из копии · ` +
        Object.entries(plan.counts || {}).map(([slug,count])=>`${slug}: ${count}`).join(' · ') +
        ` · защищённых объектов не трогаем: ${plan.protectedNotModified} · SHA256 исходника: ${plan.sourceSha256}`;
      $('lod-build-preview').hidden = false;
      $('lod-build-confirm').value = '';
      $('lod-build-confirm-label').hidden = false;
      $('lod-build-execute').hidden = false;
      $('lod-build-execute').disabled = true;
      $('lod-build-status').textContent = 'Preflight OK. Build создаст проверенный backup и отдельную Runtime XML-копию; ничего не удалит в Studio. Введи подтверждение.';
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
      $('lod-build-status').textContent = `Runtime draft создан: ${result.removedVisualMeshParts} визуальных MeshParts. Встроен клиентский FULL/LOD1 пилот. Публикация ЗАБЛОКИРОВАНА до Studio / мобильной проверки.`;
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
