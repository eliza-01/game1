/* Characters M172: UI state & actionable reports. Persistence and publication stay in their services. */
(() => {
  const STATS = [
    ['Level','level'],['MaxHP','hp'],['Damage','damage'],['Defense','defense'],
    ['AttackSpeed','attack-speed'],['RunSpeed','run-speed'],['CritChance','crit-chance'],
  ];
  let busy = false;
  const byId = id => document.getElementById(id);
  const rowNow = () => selectedRow();
  const differences = (before, after) => Object.keys(after).filter(key => Number(before[key]) !== Number(after[key]));
  const currentStats = () => characterStatsPayload();
  const identityDirty = row => !!row && (
    byId('character-id').value.trim().toLowerCase() !== row.id ||
    byId('race').value !== row.race || byId('gender').value !== row.gender ||
    byId('display-name').value.trim() !== (row.display_name || '')
  );

  function updateButtons(row) {
    const changedStats = row && differences(row.stats || {}, currentStats()).length > 0;
    const save = byId('save-character-stats');
    save.disabled = busy || !changedStats;
    save.classList.toggle('character-dirty', !!changedStats && !busy);
    const identity = byId('save-archetype');
    identity.disabled = busy || !identityDirty(row);
    identity.classList.toggle('character-dirty', !!identityDirty(row) && !busy);
    byId('register-character').disabled = busy || !state.data?.publication?.configured;
    byId('clear-form').disabled = busy;
  }

  function reset() {
    if (busy) return;
    setForm(rowNow()); // Reset unsaved values; keep selected character and its saved stats.
    byId('picked-model').textContent = 'FBX chosen during Reg + Publish.';
  }

  function openReport(title, summary, stages, recovery = null) {
    byId('character-report-title').textContent = title;
    byId('character-report-summary').textContent = summary;
    const host = byId('character-report-stages');
    host.replaceChildren();
    for (const step of stages) {
      const entry = document.createElement('div');
      entry.className = `character-report-step ${step.status}`;
      const label = document.createElement('strong');
      label.textContent = `${step.status === 'ok' ? '✓' : step.status === 'error' ? '✕' : '…'} ${step.name}`;
      const detail = document.createElement('span');
      detail.textContent = step.detail || '';
      entry.append(label,detail);
      host.appendChild(entry);
    }
    const action = byId('character-report-recovery');
    action.replaceChildren();
    if (recovery) {
      const message = document.createElement('p');
      message.textContent = recovery.message;
      action.appendChild(message);
      if (recovery.replaceId) {
        const replace = document.createElement('button');
        replace.type = 'button';
        replace.textContent = 'Replace FBX · new Model ID';
        replace.onclick = () => {byId('character-report-dialog').close();publish(true);};
        action.appendChild(replace);
        const syncOnly = document.createElement('button');
        syncOnly.type = 'button';
        syncOnly.textContent = 'Sync existing model to Studio';
        syncOnly.onclick = () => {byId('character-report-dialog').close();retryStudio(recovery.replaceId);};
        action.appendChild(syncOnly);
      }
      if (recovery.retryId) {
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = 'Retry Studio Sync';
        retry.onclick = () => retryStudio(recovery.retryId);
        action.appendChild(retry);
      }
    }
    const dlg = byId('character-report-dialog');
    if (!dlg.open) dlg.showModal();
  }

  async function saveStats() {
    const row = rowNow();
    if (!row || busy) return;
    const before = {...(row.stats || {})};
    const draft = currentStats();
    const changed = differences(before, draft);
    if (!changed.length) return;
    busy = true;
    updateButtons(row);
    openReport('Starting stats', 'Saving starting values in the project…', [{name:'Save and export',status:'pending',detail:'Waiting for registry export'}]);
    try {
      const snapshot = await request('/api/characters/'+encodeURIComponent(row.id)+'/stats', {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stats:draft}),
      });
      const updated = snapshot.items.find(item => item.id === row.id);
      if (!updated) throw Error('Saved row missing in registry response');
      state.data = {...snapshot,publication:state.data?.publication||{}};
      fillCharacterStats(updated);
      renderCharacters();
      const actual = changed.map(key => ({name:key,status:'ok',detail:`${before[key]} → ${updated.stats[key]}`}));
      openReport('Starting stats · saved',
        `Updated ${row.id}: ${changed.length} value(s).`, [
          ...actual,
          {name:'Project export',status:'ok',detail:'SQLite + assets/manifests/character-archetypes.json + src/shared/character/CharacterRegistry.luau written'},
          {name:'Studio delivery',status:'pending',detail:'Rojo propagates generated CharacterRegistry.luau; live Studio confirmation is unavailable from this endpoint. Restart Play to apply new spawn stats.'},
        ]);
    } catch (error) {
      openReport('Starting stats · failed',error.message,[{name:'Save and export',status:'error',detail:error.message}]);
    } finally {busy=false;updateButtons(rowNow());}
  }

  async function publish(forceReplacementPicker = false) {
    if (busy) return;
    const row = rowNow();
    if (!state.data?.publication?.configured) {
      openReport('Reg + Publish · unavailable','Configure Open Cloud credentials first.',[]);
      return;
    }
    if (identityDirty(row)) {
      openReport('Save Identity first','Identity changes are a separate, potentially destructive migration. Save or Reset them before publishing.',[]);
      return;
    }
    if (row && differences(row.stats || {}, currentStats()).length) {
      openReport('Unsaved starting stats', 'Save Starting Stats or Reset before model publication, so your changes are not discarded.', []);
      return;
    }
    if (row?.model_asset_id && row.status === 'PUBLISHED' && !row.model_replacement_pending && !state.sourcePath && !forceReplacementPicker) {
      openReport('Published character',`Asset ${row.model_asset_id} is already published. Choose a model replacement or synchronize the current model without uploading again.`,
        [{name:'Current Roblox asset',status:'ok',detail:row.model_asset_id}],
        {message:'Neither option overwrites the existing published Roblox asset.',replaceId:row.id});
      return;
    }
    let source = state.sourcePath || '';
    const reuse = !!row && !!row.source_path && (row.status !== 'PUBLISHED' || !!row.model_replacement_pending);
    if (!source && (!reuse || forceReplacementPicker)) {
      source = await chooseModel();
      if (!source) return;
    }
    if (row?.model_asset_id && source && !confirm(`Publish a NEW Model Asset for ${row.id}? Current asset ${row.model_asset_id} remains assigned until the new upload succeeds.`)) return;
    const characterId = row?.id || byId('character-id').value.trim().toLowerCase();
    busy = true;updateButtons(row);
    openReport('Reg + Publish · running',`Character: ${characterId}. The server is validating, registering, publishing and syncing…`,[
      {name:'Validate',status:'pending',detail:'Server operation in progress'},
      {name:'Register',status:'pending',detail:'Awaiting validation'},
      {name:'Publish',status:'pending',detail:'Awaiting Roblox Open Cloud'},
      {name:'Studio',status:'pending',detail:'Awaiting published model'},
    ]);
    try {
      const result = await request('/api/characters/workflow',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({existingId:row?.id||'',id:characterId,
          displayName:byId('display-name').value,race:byId('race').value,gender:byId('gender').value,
          sourcePath:source,description:byId('publication-description').value,stats:currentStats()}),
      });
      state.selected = result.characterId || row?.id || null;
      if (result.characterId) state.sourcePath = '';
      try {await loadCharacters();if (selectedRow()) setForm(selectedRow());} catch (reloadError) {toast('Refresh failed: '+reloadError.message,true);}
      const assetChange = result.newAssetId
        ? (result.previousAssetId && result.previousAssetId !== result.newAssetId
            ? ` · Model Asset ${result.previousAssetId} → ${result.newAssetId}`
            : ` · Model Asset ${result.newAssetId}`) : '';
      const stages = (result.stages || []).map(step => step.name === 'studio' && step.status === 'ok' && result.studio?.destination
        ? {...step,detail:`${step.detail} · ${Array.isArray(result.studio.destination)?result.studio.destination.join('/'):String(result.studio.destination)}`}
        : step);
      openReport(result.ok?'Reg + Publish · completed':'Reg + Publish · attention required',
        `${result.characterId||characterId}${assetChange}${result.error?' · '+result.error:''}`,
        stages,result.ok?null:{message:result.recovery||'Review the failed stage and retry.',retryId:result.failedStage==='studio'?result.characterId:null});
    } catch (error) {
      openReport('Reg + Publish · request failed',error.message,[{name:'HTTP request',status:'error',detail:'Connection failed or server returned an unexpected response. Refresh registry before retrying.'}]);
    } finally {busy=false;updateButtons(rowNow());}
  }

  async function retryStudio(characterId) {
    if (!characterId || busy) return;
    busy=true;updateButtons(rowNow());
    openReport('Studio Sync · running',`Syncing existing published asset for ${characterId}…`,[{name:'Studio',status:'pending',detail:'Waiting for Studio Bridge'}]);
    try {
      const result = await request('/api/characters/'+encodeURIComponent(characterId)+'/sync',{method:'POST'});
      openReport('Studio Sync · completed',`Model for ${characterId} synchronized.`,[{name:'Studio',status:'ok',detail:String(result.studio?.destination||'Published model loaded and validated')}]);
    } catch (error) {
      openReport('Studio Sync · failed',error.message,[{name:'Studio',status:'error',detail:error.message}],{message:'No republish needed. Repair the Studio connection and retry.',retryId:characterId});
    } finally {busy=false;updateButtons(rowNow());}
  }

  const ids = STATS.map(([,id]) => 'character-stat-'+id);
  ids.forEach(id => byId(id).addEventListener('input',()=>updateButtons(rowNow())));
  byId('character-report-close').onclick = () => byId('character-report-dialog').close();
  const tooltip = byId('character-tooltip');
  const hideTooltip = () => {tooltip.hidden=true;};
  document.querySelectorAll('#characters-view [data-character-tip]').forEach(button => {
    const show = () => {tooltip.textContent=button.dataset.characterTip;tooltip.classList.toggle('character-tooltip-atlas',button.hasAttribute('data-character-atlas-guide'));tooltip.hidden=false;const r=button.getBoundingClientRect();place({clientX:r.right,clientY:r.bottom});};
    const place = event => {const x=Math.max(10,Math.min(window.innerWidth-tooltip.offsetWidth-10,event.clientX+12));const y=Math.max(10,Math.min(window.innerHeight-tooltip.offsetHeight-10,event.clientY+14));tooltip.style.left=x+'px';tooltip.style.top=y+'px';};
    button.addEventListener('mouseenter',show);button.addEventListener('mousemove',place);
    button.addEventListener('mouseleave',hideTooltip);button.addEventListener('focus',show);button.addEventListener('blur',hideTooltip);
  });
  window.game1CharacterWorkflow = {publish,saveStats,reset,updateButtons,retryStudio};
  updateButtons(rowNow());
})();
