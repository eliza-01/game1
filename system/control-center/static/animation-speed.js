const animationSpeedState={data:null,saving:new Set()};
function animationSpeedNumber(value){const n=Number(value);return Number.isFinite(n)?n:0}
function animationSpeedFormat(value){const n=animationSpeedNumber(value);return Math.abs(n-Math.round(n))<0.0001?String(Math.round(n)):String(Number(n.toFixed(4)))}
function animationSpeedRender(){
  const host=$('animation-speed-profiles');if(!host)return;
  const profiles=animationSpeedState.data?.profiles||[];
  if(!profiles.length){host.innerHTML='<span class="muted">no animation speed scaling rules.</span>';return}
  host.innerHTML=profiles.map(profile=>{
    const rows=(profile.rules||[]).map(rule=>{
      const key=[profile.targetType,profile.targetId,rule.channel].join(':');
      const units=animationSpeedFormat(rule.unitsPerPercent);
      return `<div class="details-grid" data-animation-speed-key="${esc(key)}"><div><b>${esc(rule.label||rule.channel)}</b><span>${esc(rule.stat)} · ${esc(rule.channel)} animations</span></div><div><b>1% playback per</b><span><input data-animation-speed-units type="number" min="0.001" max="100000" step="0.01" value="${esc(units)}"> stat units</span></div><div><b>formula</b><span>playback % = ${esc(rule.stat)} / ${esc(units)}</span></div><div><button data-animation-speed-save class="primary" type="button">save</button></div></div>`;
    }).join('');
    return `<div class="section-title"><div><span>${esc(profile.targetType)}</span><h3>${esc(profile.displayName||profile.targetId)}</h3></div><span class="pill">${esc(profile.targetId)}</span></div>${rows}`;
  }).join('<hr class="card-separator">');
  for(const profile of profiles){for(const rule of profile.rules||[]){
    const key=[profile.targetType,profile.targetId,rule.channel].join(':');
    const row=[...host.querySelectorAll('[data-animation-speed-key]')].find(el=>el.dataset.animationSpeedKey===key);if(!row)continue;
    const input=row.querySelector('[data-animation-speed-units]'),button=row.querySelector('[data-animation-speed-save]');
    const busy=animationSpeedState.saving.has(key);button.disabled=busy;button.textContent=busy?'saving…':'save';
    button.onclick=()=>animationSpeedSave(profile,rule,input);
    input.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();animationSpeedSave(profile,rule,input)}};
  }}
}
async function animationSpeedLoad(){try{animationSpeedState.data=await request('/api/animation-speed-scaling');animationSpeedRender()}catch(error){toast(error.message,true)}}
async function animationSpeedSave(profile,rule,input){
  const units=Number(input.value);if(!Number.isFinite(units)||units<0.001||units>100000){toast('units per 1% must be 0.001..100000',true);return}
  const key=[profile.targetType,profile.targetId,rule.channel].join(':');animationSpeedState.saving.add(key);animationSpeedRender();
  try{animationSpeedState.data=await request('/api/animation-speed-scaling',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targetType:profile.targetType,targetId:profile.targetId,channel:rule.channel,unitsPerPercent:units})});toast(`${profile.displayName||profile.targetId} · ${rule.label||rule.channel}: 1% per ${animationSpeedFormat(units)} ${rule.stat}`)}catch(error){toast(error.message,true)}finally{animationSpeedState.saving.delete(key);animationSpeedRender()}
}
window.game1AnimationSpeedLoad=animationSpeedLoad;
$('refresh-animation-speed').onclick=animationSpeedLoad;
