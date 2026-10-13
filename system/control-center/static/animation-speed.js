const animationSpeedState={data:null,saving:new Set(),search:""};
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
      return `<article class="animation-speed-rule" data-animation-speed-key="${esc(key)}">
        <div class="animation-speed-rule-head">
          <div><span>animation</span><h4>${esc(meta.title)}</h4><small>${esc(meta.description)}</small></div>
          <span class="animation-speed-channel">${esc(rule.channel)}</span>
        </div>
        <div class="animation-speed-fields">
          <div class="animation-speed-field animation-speed-readonly"><b>Gameplay stat</b><strong>${esc(rule.stat)}</strong><small>Gameplay value that controls playback speed for this animation only.</small></div>
          <label class="animation-speed-field"><b>Stat units for +1% playback</b><input data-animation-speed-units type="number" min="0.001" max="100000" step="0.01" value="${esc(units)}"><small>Lower value = faster playback for the same ${esc(rule.stat)}.</small></label>
          <div class="animation-speed-field"><b>Playback formula</b><code>playback % = ${esc(rule.stat)} ÷ ${esc(units)}</code><small>This rule is evaluated at runtime from the current gameplay stat.</small></div>
          <div class="animation-speed-field"><b>Example</b><strong>${esc(animationSpeedExample(rule,Number(units)))}</strong><small>Example uses a stat value of 100 only to make the scale easy to compare.</small></div>
        </div>
        <div class="animation-speed-rule-actions"><span>applies to <b>${esc(meta.title)}</b> only</span><button data-animation-speed-save class="primary" type="button">save ${esc(meta.title)}</button></div>
      </article>`;
    }).join('');
    const explanation=profile.targetType==='humanoid'?'Shared across all Characters and NPCs; each animation state has an independent rule.':'Separate scaling rules for this monster profile.';
    return `<section class="animation-speed-profile"><div class="animation-speed-profile-head"><div><span>${esc(profile.targetType)}</span><h3>${esc(profile.displayName||profile.targetId)}</h3><small>${esc(explanation)}</small></div><span class="pill">${esc(profile.targetId)}</span></div><div class="animation-speed-rule-grid">${cards}</div></section>`;
  }).join('');
  for(const profile of profiles){for(const rule of profile.rules||[]){
    const key=[profile.targetType,profile.targetId,rule.channel].join(':');
    const row=[...host.querySelectorAll('[data-animation-speed-key]')].find(el=>el.dataset.animationSpeedKey===key);if(!row)continue;
    const input=row.querySelector('[data-animation-speed-units]'),button=row.querySelector('[data-animation-speed-save]');
    const busy=animationSpeedState.saving.has(key);button.disabled=busy;button.textContent=busy?'saving…':`save ${animationSpeedRuleMeta(rule).title}`;
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
function customScalingRender(){
  const list=$('custom-scaling-rows'), results=$('custom-scaling-results');
  if(!list||!results)return;
  const catalog=customScalingCatalog(), saved=customScalingSaved();
  const byId=new Map(catalog.map(c=>[c.assetId,c]));
  const term=animationSpeedState.search.trim().toLowerCase();
  const matches=term?catalog.filter(c=>
    [c.name,c.subject,c.kind,c.channel,c.assetId,c.clipId].some(x=>String(x||'').toLowerCase().includes(term))
  ).slice(0,30):[];
  results.hidden=!term;
  results.innerHTML=term?(matches.length?matches.map(c=>
    `<button type="button" data-custom-pick="${esc(c.assetId)}"><b>${esc(c.name)}</b><small>${esc(c.kind)} / ${esc(c.subject)} / ${esc(c.channel)} · ${esc(c.assetId)}</small></button>`
  ).join(''):'<span class="muted">No published animations match.</span>'):'';
  for(const button of results.querySelectorAll('[data-custom-pick]'))button.onclick=()=>{
    const aid=button.dataset.customPick;
    if(!saved.some(row=>row.assetId===aid))saved.push({assetId:aid,...customScalingInherited(byId.get(aid)),_draft:true});
    animationSpeedState.search='';$('custom-scaling-search').value='';customScalingRender();
    list.querySelector(`[data-custom-row="${aid}"]`)?.scrollIntoView({block:'nearest'});
  };
  list.innerHTML=saved.length?saved.map(row=>{
    const c=byId.get(row.assetId);
    return `<article class="animation-speed-rule" data-custom-row="${esc(row.assetId)}">
       <div class="animation-speed-rule-head"><div><span>${esc(c?.kind||'published')} / ${esc(c?.subject||'registered')}</span><h4>${esc(c?.name||row.assetId)}</h4><small>${esc(c?.channel||'')} · Roblox Animation ID ${esc(row.assetId)}</small></div><span class="animation-speed-channel">${row._draft?'new':'custom'}</span></div>
       <div class="animation-speed-fields">
        <label class="animation-speed-field"><b>Gameplay stat</b><select data-custom-stat><option value="AttackSpeed" ${row.stat==='AttackSpeed'?'selected':''}>AttackSpeed</option><option value="RunSpeed" ${row.stat==='RunSpeed'?'selected':''}>RunSpeed</option></select></label>
        <label class="animation-speed-field"><b>Stat units for +1% playback</b><input data-custom-units type="number" min="0.001" max="1000" step="0.01" value="${esc(animationSpeedFormat(row.unitsPerPercent))}"></label>
       </div><div class="animation-speed-rule-actions"><span>override only this animation</span><div class="actions"><button data-custom-remove type="button">${row._draft?'cancel':'remove override'}</button><button data-custom-apply class="primary" type="button">apply</button></div></div>
    </article>`;
  }).join(''):'<span class="muted">No custom overrides. Search for a published animation above.</span>';
  for(const section of list.querySelectorAll('[data-custom-row]')){
    const aid=section.dataset.customRow;
    section.querySelector('[data-custom-apply]').onclick=()=>customScalingSave(aid,section,false);
    section.querySelector('[data-custom-remove]').onclick=()=>customScalingSave(aid,section,true);
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
$('custom-scaling-search').oninput=e=>{animationSpeedState.search=e.target.value;customScalingRender()};
