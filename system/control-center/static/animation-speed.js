const animationSpeedState={data:null,saving:new Set(),search:"",catalogKind:"",catalogSubject:"",catalogPage:0,overrideFilter:"",overridePage:0};
const animationSpeedChannelMeta={
  run:{title:'Run',description:'Running movement animations.'},
  walk:{title:'Walk',description:'Walking movement animations.'},
  combat_idle:{title:'Combat Idle',description:'Combat stance animation for Characters and NPCs.'},
  attack:{title:'Attack',description:'Attack animations. Scales independently from Combat Idle.'},
};
function animationSpeedNumber(value){const n=Number(value);return Number.isFinite(n)?n:0}
function animationSpeedFormat(value){const n=animationSpeedNumber(value);return Math.abs(n-Math.round(n))<0.0001?String(Math.round(n)):String(Number(n.toFixed(4)))}
function animationSpeedRuleMeta(rule){return animationSpeedChannelMeta[rule.channel]||{title:rule.label||rule.channel,description:`${rule.channel} animation state.`}}
function animationSpeedExample(rule,units){const sample=100;const playback=units>0?sample/units:0;return `${rule.stat} ${sample} → ${animationSpeedFormat(playback)}% playback`}
function animationSpeedRender(){
  const host=$('animation-speed-profiles');if(!host)return;
  const profiles=animationSpeedState.data?.profiles||[];
  if(!profiles.length){host.innerHTML='<span class="muted">no animation speed scaling rules.</span>';return}
  host.innerHTML=profiles.map(profile=>{
    const cards=(profile.rules||[]).map(rule=>{
      const key=[profile.targetType,profile.targetId,rule.channel].join(':');
      const units=animationSpeedFormat(rule.unitsPerPercent);
      const meta=animationSpeedRuleMeta(rule);
      return `<article class="animation-speed-rule animation-speed-compact" data-animation-speed-key="${esc(key)}">
        <div class="animation-speed-compact-intro"><h4>${esc(meta.title)}</h4><small>${esc(rule.stat)} · ${esc(animationSpeedExample(rule,Number(units)))}</small></div>
        <label class="animation-speed-compact-input"><span>Единиц / +1%</span><input data-animation-speed-units type="number" min="0.001" max="100000" step="0.01" value="${esc(units)}"></label>
        <button data-animation-speed-save class="primary" type="button">Сохранить</button>
      </article>`;
    }).join('');
    const explanation=(profile.targetType==='humanoid'?'Общее правило для персонажей и NPC.':'Правила этого монстра.')+' Playback formula: стат ÷ единиц = скорость %.';
    return `<section class="animation-speed-profile"><div class="animation-speed-profile-head"><div><span>${esc(profile.targetType)}</span><h3>${esc(profile.displayName||profile.targetId)}</h3><small>${esc(explanation)}</small></div><span class="pill">${esc(profile.targetId)}</span></div><div class="animation-speed-rule-grid">${cards}</div></section>`;
  }).join('');
  for(const profile of profiles){for(const rule of profile.rules||[]){
    const key=[profile.targetType,profile.targetId,rule.channel].join(':');
    const row=[...host.querySelectorAll('[data-animation-speed-key]')].find(el=>el.dataset.animationSpeedKey===key);if(!row)continue;
    const input=row.querySelector('[data-animation-speed-units]'),button=row.querySelector('[data-animation-speed-save]');
    const busy=animationSpeedState.saving.has(key);button.disabled=busy;button.textContent=busy?'Сохранение…':'Сохранить';
    button.onclick=()=>animationSpeedSave(profile,rule,input);
    input.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();animationSpeedSave(profile,rule,input)}};
  }}
}
async function animationSpeedLoad(){try{animationSpeedState.data=await request('/api/animation-speed-scaling');animationSpeedRender();customScalingRender()}catch(error){toast(error.message,true)}}
async function animationSpeedSave(profile,rule,input){
  const units=Number(input.value);if(!Number.isFinite(units)||units<0.001||units>100000){toast('stat units for +1% playback must be 0.001..100000',true);return}
  const key=[profile.targetType,profile.targetId,rule.channel].join(':');animationSpeedState.saving.add(key);animationSpeedRender();
  try{animationSpeedState.data=await request('/api/animation-speed-scaling',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targetType:profile.targetType,targetId:profile.targetId,channel:rule.channel,unitsPerPercent:units})});toast(`${profile.displayName||profile.targetId} · ${animationSpeedRuleMeta(rule).title}: +1% playback per ${animationSpeedFormat(units)} ${rule.stat}`)}catch(error){toast(error.message,true)}finally{animationSpeedState.saving.delete(key);animationSpeedRender();customScalingRender()}
}
window.game1AnimationSpeedLoad=animationSpeedLoad;
$('refresh-animation-speed').onclick=animationSpeedLoad;

// Clip-level overrides. The default state rules are intentionally left untouched.
function customScalingCatalog(){return animationSpeedState.data?.catalog||[]}
function customScalingSaved(){
  if(!animationSpeedState.data)return [];
  // Newly migrated projects have no customScaling key until the first save.
  // Keep draft rows in the actual page state, not in a throwaway fallback array.
  if(!Array.isArray(animationSpeedState.data.customScaling))animationSpeedState.data.customScaling=[];
  return animationSpeedState.data.customScaling;
}
function customScalingInherited(clip){
  const type=clip.kind==='monster'?'monster':'humanoid';
  const id=clip.kind==='monster'?clip.subject:'all';
  const profile=(animationSpeedState.data?.profiles||[]).find(p=>p.targetType===type&&p.targetId===id);
  const rule=(profile?.rules||[]).find(r=>r.channel===clip.channel);
  return {stat:rule?.stat||clip.stat||'AttackSpeed',unitsPerPercent:rule?.unitsPerPercent||1};
}
const CUSTOM_SCALING_PAGE_SIZE=40;
function customScalingRender(){
  const list=$('custom-scaling-rows'),results=$('custom-scaling-results');
  if(!list||!results)return;
  const catalog=customScalingCatalog(),saved=customScalingSaved();
  const byId=new Map(catalog.map(c=>[c.assetId,c]));
  // Published catalog is always visible. Custom overrides below are only a
  // subset; requiring a typed query hid newly registered social/common clips.
  const selectors=window.game1AnimationSpeedCatalog;
  const kind=animationSpeedState.catalogKind;
  const subjectPicker=$('custom-scaling-subject');
  const subjects=selectors.subjects(catalog,kind);
  if(animationSpeedState.catalogSubject&&!subjects.includes(animationSpeedState.catalogSubject)){
    animationSpeedState.catalogSubject='';
  }
  if(subjectPicker){
    subjectPicker.innerHTML='<option value="">All profiles</option>'+subjects.map(s=>
      `<option value="${esc(s)}" ${s===animationSpeedState.catalogSubject?'selected':''}>${esc(s)}</option>`
    ).join('');
  }
  const filteredCatalog=selectors.visible(catalog,{
    search:animationSpeedState.search,kind,subject:animationSpeedState.catalogSubject
  });
  const shown=selectors.page(filteredCatalog,animationSpeedState.catalogPage,24);
  animationSpeedState.catalogPage=shown.number;
  const catalogCount=$('custom-scaling-catalog-count');
  if(catalogCount)catalogCount.textContent=`${filteredCatalog.length} / ${catalog.length} published animations`;
  results.hidden=false;
  results.innerHTML=shown.rows.length?shown.rows.map(c=>{
    const existing=saved.find(row=>row.assetId===c.assetId);
    const policy=customScalingInherited(c);
    const hasStateRule=(animationSpeedState.data?.profiles||[]).some(p=>
      p.targetType===(c.kind==='monster'?'monster':'humanoid')&&
      p.targetId===(c.kind==='monster'?c.subject:'all')&&
      (p.rules||[]).some(r=>r.channel===c.channel)
    );
    const defaultLabel=hasStateRule?`State rule · ${policy.stat}`:'Default · 100%';
    return `<div class="custom-scaling-catalog-row" role="listitem">
      <div class="custom-scaling-clip"><strong>${esc(c.subject)} · ${esc(c.name)}</strong>
      <small>${esc(c.kind)} / ${esc(c.scope||c.channel)}${c.weaponSet?' / '+esc(c.weaponSet):''} / ${esc(c.channel)} · ${esc(c.assetId)}${c.availableFor?.length>1?' · for '+esc(c.availableFor.join(', ')):''}</small></div>
      <span class="custom-scaling-catalog-status ${existing?'active':''}">${esc(existing?'Custom · '+existing.stat:defaultLabel)}</span>
      <button type="button" data-custom-pick="${esc(c.assetId)}">${existing?'Edit':'Configure'}</button>
    </div>`;
  }).join(''):'<span class="muted">No published animations match. Change filters or refresh the catalog.</span>';
  const catalogPages=$('custom-scaling-catalog-pages');
  if(catalogPages){
    catalogPages.hidden=shown.pages<=1;
    catalogPages.innerHTML=`<button type="button" data-catalog-page="prev" ${shown.number===0?'disabled':''}>←</button><span>${shown.number+1} / ${shown.pages}</span><button type="button" data-catalog-page="next" ${shown.number>=shown.pages-1?'disabled':''}>→</button>`;
    for(const button of catalogPages.querySelectorAll('[data-catalog-page]'))button.onclick=()=>{
      animationSpeedState.catalogPage+=button.dataset.catalogPage==='next'?1:-1;
      customScalingRender();
    };
  }
  for(const button of results.querySelectorAll('[data-custom-pick]'))button.onclick=()=>{
    const aid=button.dataset.customPick;
    if(!saved.some(row=>row.assetId===aid))saved.push({assetId:aid,...customScalingInherited(byId.get(aid)),_draft:true});
    animationSpeedState.overrideFilter='';
    const order=[...saved].sort((a,b)=>(byId.get(a.assetId)?.name||a.assetId).localeCompare(byId.get(b.assetId)?.name||b.assetId));
    animationSpeedState.overridePage=Math.floor(order.findIndex(row=>row.assetId===aid)/CUSTOM_SCALING_PAGE_SIZE);
    const filter=$('custom-scaling-filter');if(filter)filter.value='';
    customScalingRender();
    list.querySelector(`[data-custom-row="${aid}"]`)?.scrollIntoView({block:'nearest'});
  };
  const query=animationSpeedState.overrideFilter.trim().toLowerCase();
  const filtered=saved.filter(row=>{
    const c=byId.get(row.assetId);
    return !query||[row.assetId,row.stat,c?.name,c?.subject,c?.kind,c?.channel,c?.clipId]
      .some(value=>String(value||'').toLowerCase().includes(query));
  }).sort((a,b)=>{
    const ca=byId.get(a.assetId),cb=byId.get(b.assetId);
    return String(ca?.name||a.assetId).localeCompare(String(cb?.name||b.assetId));
  });
  const pages=Math.max(1,Math.ceil(filtered.length/CUSTOM_SCALING_PAGE_SIZE));
  animationSpeedState.overridePage=Math.min(animationSpeedState.overridePage,pages-1);
  const start=animationSpeedState.overridePage*CUSTOM_SCALING_PAGE_SIZE;
  const pageRows=filtered.slice(start,start+CUSTOM_SCALING_PAGE_SIZE);
  const status=$('custom-scaling-count');
  if(status)status.textContent=`${filtered.length} / ${saved.length} overrides`;
  list.innerHTML=pageRows.length?`<div class="custom-scaling-table" role="table" aria-label="Clip scaling overrides">
    <div class="custom-scaling-table-head" role="row"><span>Анимация</span><span>Stat</span><span>Ед./1%</span><span>Действия</span></div>
    ${pageRows.map(row=>{
      const c=byId.get(row.assetId);
      return `<div class="custom-scaling-table-row" role="row" data-custom-row="${esc(row.assetId)}">
        <div class="custom-scaling-clip" title="${esc(c?.name||row.assetId)}"><strong>${esc(c?.name||row.assetId)}</strong><small>${esc(c?.subject||c?.kind||'registered')} · ${esc(c?.channel||'')} · ${esc(row.assetId)}${row._draft?' · NEW':''}</small></div>
        <label class="custom-scaling-cell"><span class="sr-only">Gameplay stat</span><select aria-label="Stat for ${esc(c?.name||row.assetId)}" data-custom-stat><option value="AttackSpeed" ${row.stat==='AttackSpeed'?'selected':''}>AttackSpeed</option><option value="RunSpeed" ${row.stat==='RunSpeed'?'selected':''}>RunSpeed</option></select></label>
        <label class="custom-scaling-cell"><span class="sr-only">Units per 1 percent</span><input aria-label="Units per 1% for ${esc(c?.name||row.assetId)}" data-custom-units type="number" min="0.001" max="1000" step="0.01" value="${esc(animationSpeedFormat(row.unitsPerPercent))}"></label>
        <div class="custom-scaling-table-actions"><button data-custom-apply class="primary" type="button" title="Сохранить override">Save</button><button data-custom-remove type="button" title="${row._draft?'Отменить':'Удалить override'}">${row._draft?'Cancel':'Remove'}</button></div>
      </div>`;
    }).join('')}
  </div>`:'<span class="muted">'+(saved.length?'No overrides match the filter.':'No custom overrides. Search for a published animation above.')+'</span>';
  const pagination=$('custom-scaling-pages');
  if(pagination){
    pagination.hidden=filtered.length<=CUSTOM_SCALING_PAGE_SIZE;
    pagination.innerHTML=`<button type="button" data-custom-page="prev" ${animationSpeedState.overridePage===0?'disabled':''}>←</button><span>${animationSpeedState.overridePage+1} / ${pages}</span><button type="button" data-custom-page="next" ${animationSpeedState.overridePage>=pages-1?'disabled':''}>→</button>`;
    for(const button of pagination.querySelectorAll('[data-custom-page]'))button.onclick=()=>{
      animationSpeedState.overridePage+=button.dataset.customPage==='next'?1:-1;
      customScalingRender();
    };
  }
  for(const section of list.querySelectorAll('[data-custom-row]')){
    const aid=section.dataset.customRow;
    section.querySelector('[data-custom-apply]').onclick=()=>customScalingSave(aid,section,false);
    section.querySelector('[data-custom-remove]').onclick=()=>customScalingSave(aid,section,true);
    for(const input of section.querySelectorAll('[data-custom-units],[data-custom-stat]')){
      input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();customScalingSave(aid,section,false)}});
    }
  }
}
async function customScalingSave(assetId,section,remove){
  const entry=customScalingSaved().find(r=>r.assetId===assetId);
  if(remove&&entry?._draft){animationSpeedState.data.customScaling=customScalingSaved().filter(r=>r!==entry);customScalingRender();return}
  const stat=section.querySelector('[data-custom-stat]').value;
  const units=Number(section.querySelector('[data-custom-units]').value);
  if(!remove&&(!Number.isFinite(units)||units<0.001||units>1000)){toast('units must be 0.001..1000',true);return}
  const action=section.querySelector('[data-custom-apply]');action.disabled=true;
  try{
    animationSpeedState.data=await request('/api/animation-speed-scaling/custom',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assetId,stat,unitsPerPercent:units,delete:remove})});
    toast(remove?'Custom override removed; state default restored.':'Custom animation scaling saved.');
    animationSpeedRender();customScalingRender();
  }catch(error){toast(error.message,true);action.disabled=false}
}
$('custom-scaling-search').oninput=e=>{animationSpeedState.search=e.target.value;animationSpeedState.catalogPage=0;customScalingRender()};
$('custom-scaling-kind').onchange=e=>{animationSpeedState.catalogKind=e.target.value;animationSpeedState.catalogSubject='';animationSpeedState.catalogPage=0;customScalingRender()};
$('custom-scaling-subject').onchange=e=>{animationSpeedState.catalogSubject=e.target.value;animationSpeedState.catalogPage=0;customScalingRender()};

// Controls live beside the existing list, so older Control Center markup is
// still compatible without copying/replacing the entire HTML template.
const customRowsHost=$('custom-scaling-rows');
if(customRowsHost&&!$('custom-scaling-filter')){
  customRowsHost.insertAdjacentHTML('beforebegin',`<div class="custom-scaling-toolbar">
    <label>Filter overrides <input type="search" id="custom-scaling-filter" autocomplete="off" placeholder="name, subject, channel, ID"></label>
    <span id="custom-scaling-count" aria-live="polite">0 overrides</span>
  </div>`);
  customRowsHost.insertAdjacentHTML('afterend','<div id="custom-scaling-pages" class="custom-scaling-pages" hidden></div>');
}
$('custom-scaling-filter').oninput=e=>{
  animationSpeedState.overrideFilter=e.target.value;
  animationSpeedState.overridePage=0;
  customScalingRender();
};
