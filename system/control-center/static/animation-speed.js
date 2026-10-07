const animationSpeedState={data:null,saving:new Set()};
const animationSpeedChannelMeta={
  run:{title:'Run',description:'Running movement animations.'},
  walk:{title:'Walk',description:'Walking movement animations.'},
  combat_idle:{title:'Combat Idle',description:'Idle animation while the character is in combat stance.'},
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
    return `<section class="animation-speed-profile"><div class="animation-speed-profile-head"><div><span>${esc(profile.targetType)}</span><h3>${esc(profile.displayName||profile.targetId)}</h3><small>Each animation block has its own playback scaling rule.</small></div><span class="pill">${esc(profile.targetId)}</span></div><div class="animation-speed-rule-grid">${cards}</div></section>`;
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
async function animationSpeedLoad(){try{animationSpeedState.data=await request('/api/animation-speed-scaling');animationSpeedRender()}catch(error){toast(error.message,true)}}
async function animationSpeedSave(profile,rule,input){
  const units=Number(input.value);if(!Number.isFinite(units)||units<0.001||units>100000){toast('stat units for +1% playback must be 0.001..100000',true);return}
  const key=[profile.targetType,profile.targetId,rule.channel].join(':');animationSpeedState.saving.add(key);animationSpeedRender();
  try{animationSpeedState.data=await request('/api/animation-speed-scaling',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({targetType:profile.targetType,targetId:profile.targetId,channel:rule.channel,unitsPerPercent:units})});toast(`${profile.displayName||profile.targetId} · ${animationSpeedRuleMeta(rule).title}: +1% playback per ${animationSpeedFormat(units)} ${rule.stat}`)}catch(error){toast(error.message,true)}finally{animationSpeedState.saving.delete(key);animationSpeedRender()}
}
window.game1AnimationSpeedLoad=animationSpeedLoad;
$('refresh-animation-speed').onclick=animationSpeedLoad;
