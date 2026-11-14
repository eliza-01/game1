/* M351 · Location Assets Instance Manager.
 * All operations are explicit, preview-token guarded Studio Edit actions.
 * Local UI never manufactures placement paths, transforms or published IDs.
 */
(() => {
  const id = key => document.getElementById(key);
  const state = {busy:false, preview:null, assets:[]};
  const fields = ['li-source','li-target','li-scope'];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const status = text => {id('li-status').textContent = text;};
  function clearAnchors() {
    id('li-anchor').replaceChildren(new Option('Pivot новой Model', 'model'));
  }
  function loadAnchors(options) {
    const anchor = id('li-anchor');
    anchor.replaceChildren();
    for (const option of options) {
      anchor.add(new Option(option.label, option.id));
    }
    anchor.value='model';
  }
  function reset() {
    state.preview = null;
    clearAnchors();
    id('li-replace').disabled = true;
    id('li-placements').textContent = 'Сначала Preview.';
    if(!state.busy) status('Настройки изменились. Выполни Preview заново.');
  }
  function refresh(rows) {
    state.assets = (rows || []).filter(row =>
      ['PUBLISHED','UPDATE_AVAILABLE'].includes(row.status) && row.model_asset_id);
    for(const field of ['li-source','li-target']) {
      const select = id(field);
      const remembered = select.value;
      select.replaceChildren(new Option('Выбери опубликованный ассет', ''));
      for(const row of state.assets) {
        if(field === 'li-target' && row.status !== 'PUBLISHED') continue;
        select.add(new Option(`${row.slug} · ${row.model_asset_id}`, row.slug));
      }
      select.value = [...select.options].some(opt => opt.value === remembered) ? remembered : '';
    }
    reset();
  }
  async function send(phase, token) {
    const response = await fetch('/api/location-instance-manager', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({phase,sourceSlug:id('li-source').value,targetSlug:id('li-target').value,
        scope:id('li-scope').value,scanToken:token,anchorId:id('li-anchor').value}),
    });
    let data = {};
    try {data=await response.json();} catch {}
    if(!response.ok) throw Error(data.error || `HTTP ${response.status}`);
    return data.studio;
  }
  function showChoiceStatus() {
    const p = state.preview;
    if(!p) return;
    const choice = id('li-anchor');
    status(`Готово к замене: ${p.count} Model. Изменений пока нет.\n`+
      `${p.source} → ${p.target}. Pivot исходной Model ← ${choice.selectedOptions[0]?.textContent || 'Pivot новой Model'}.\n`+
      `Из исходной публикации восстановлены Pivot: ${p.normalizedPivots}, ручной MeshPart.Size: ${p.preservedManualSizes}.\n`+
      `Model scale и родительский каталог сохраняются. Переиздание конфликтующих Placement ID: ${p.reassignedIds}.\n`+
      'Исходные размещения не изменены. Неподдерживаемые размеры и оси блокируются до Replace.');
  }
  async function preview() {
    if(state.busy) return;
    const source = id('li-source').value, target = id('li-target').value;
    if(!source || !target || source === target) {
      status('Выбери два разных опубликованных Location Assets.'); return;
    }
    state.busy = true; id('li-preview').disabled = true; id('li-replace').disabled = true;
    state.preview = null;
    clearAnchors();
    status('Проверка старых размещений и поиск Pivot новой опубликованной модели…');
    try {
      const data = await send('preview','');
      if(!data.scanToken || !Array.isArray(data.placements) || data.count !== data.placements.length ||
        !Array.isArray(data.anchorOptions) || data.anchorOptions[0]?.id !== 'model')
        throw Error('Studio вернула неполный Preview');
      loadAnchors(data.anchorOptions);
      state.preview = {token:data.scanToken,source,target,scope:id('li-scope').value,
        count:data.count,reassignedIds:data.reassignedIds || 0,
        normalizedPivots:data.normalizedPivots || 0,
        preservedManualSizes:data.preservedManualSizes || 0};
      showChoiceStatus();
      id('li-placements').innerHTML = data.placements.map(row =>
        `<div class="location-instance-placement"><b>${escape(row.name)}</b> · ${escape(row.placementId)}`+
        `${row.newPlacementId && row.newPlacementId !== row.placementId ?
          ` <strong>→ новый Placement ID ${escape(row.newPlacementId)}</strong>` : ''}`+
        `<small>${escape(row.path)}${row.legacyPivot ? ' · исторический Pivot' : ''}`+
        `${row.manualSize ? ' · изменённый Size' : ''}</small></div>`).join('');
      id('li-replace').disabled = data.count < 1;
    } catch(error) {clearAnchors();status('Preview: '+error.message);id('li-placements').textContent='Ничего не выбрано.';}
    finally {state.busy=false;id('li-preview').disabled=false;}
  }
  async function replace() {
    const p=state.preview;
    if(state.busy || !p || p.source !== id('li-source').value ||
      p.target !== id('li-target').value || p.scope !== id('li-scope').value) return;
    const warning = `Заменить ${p.count} Model целиком?\n${p.source} → ${p.target}\n`+
      `Совместить: Pivot исходной Model ← ${id('li-anchor').selectedOptions[0]?.textContent}.\n`+
      `${p.reassignedIds ? `Исправить ${p.reassignedIds} конфликтующих Placement ID у заменяемых экземпляров.\n` : ''}`+
      `Исторический Pivot: ${p.normalizedPivots}; растянутые MeshParts: ${p.preservedManualSizes}.\n`+
      `Исходные модели будут заменены целиком (Undo возвращает их).\n`+
      `Сохрани .rbxl перед массовой заменой. Отмена — Ctrl+Z в Roblox Studio.`;
    if(!confirm(warning)) return;
    state.busy=true;id('li-preview').disabled=true;id('li-replace').disabled=true;
    status('Studio выполняет транзакционную замену Models…');
    try {
      const result=await send('replace',p.token);
      status(`Заменено ${result.changed} из ${p.count} Model. Переиздано Placement ID: ${result.reassignedIds || 0}.\n${result.note || ''}\n`+
        'Сохрани Place. Повтори Place Registry Scan для проверки.');
      id('li-placements').textContent='Операция завершена. Новый Preview покажет актуальное состояние.';
    } catch(error) {status('Replace: '+error.message+'\nМодели не должны быть изменены при ошибке preflight. Проверь Studio Output.');}
    finally {state.preview=null;state.busy=false;id('li-preview').disabled=false;}
  }
  for(const field of fields) id(field).addEventListener('change',reset);
  id('li-anchor').addEventListener('change', showChoiceStatus);
  id('li-preview').addEventListener('click',preview);
  id('li-replace').addEventListener('click',replace);
  window.game1LocationInstanceRefresh=refresh;
})();
