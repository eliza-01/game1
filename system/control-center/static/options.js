const game1OptionsState={data:null,saving:false,debugStamp:0,hpDevice:"desktop",hpDrafts:null};
const GAME1_CAMERA_FIELDS=[
  ['targetHeight','Target height','studs',0,12,0.25],
  ['distance','Camera distance','studs',4,18,0.25],
  ['pitchDegrees','Start pitch','degrees',-65,60,1],
  ['characterX','Character X','screen',0.2,0.8,0.01],
  ['characterY','Character Y','screen',0.2,0.8,0.01],
  ['cursorX','Aim cursor X','screen',0.1,0.9,0.01],
  ['cursorY','Aim cursor Y','screen',0.1,0.9,0.01],
];
function game1OptionNumber(id,fallback){const value=Number($(id).value);return Number.isFinite(value)?value:fallback}
function game1CameraRead(){
  const data={};
  for(const [key,, ,low,high] of GAME1_CAMERA_FIELDS){
    const el=$('option-camera-'+key);
    const value=Number(el.value);
    if(!el.value.trim()||!Number.isFinite(value)||value<low||value>high)throw Error(`${key}: expected ${low}–${high}`);
    data[key]=value;
  }
  return data;
}
function game1CameraFill(data){
  for(const [key] of GAME1_CAMERA_FIELDS){
    if(data?.[key]!==undefined)$('option-camera-'+key).value=String(data[key]);
  }
}
function game1CameraDraftStatus(data){
  const status=$('option-camera-draft-status');
  if(!status)return;
  const draft=data?.cameraDebugDraft;
  if(!draft){status.textContent='No Studio Play camera draft yet.';return;}
  const stamp=data.cameraDebugDraftAt||0;
  const date=stamp?new Date(stamp*1000).toLocaleTimeString():'';
  status.textContent=`Studio Debug draft received ${date} · not saved. Click Import Studio Debug, then Save.`;
  game1OptionsState.debugStamp=stamp;
}
function game1OptionsRender(){
  const data=game1OptionsState.data||{};
  const combat=data.combat||{};
  const life=data.characterAnimations||{};
  $('option-combat-state-duration').value=String(combat.stateDurationSeconds??6);
  $('option-character-death-playback').value=String(life.deathPlaybackPercent??100);
  $('option-character-revive-playback').value=String(life.revivePlaybackPercent??100);
  game1CameraFill(data.camera||{});
  const select=$('option-camera-presets');
  const current=select.value;
  select.innerHTML='<option value="">Choose saved preset…</option>'+(data.cameraPresets||[])
    .map(p=>`<option value="${esc(p.name)}">${esc(p.name)}</option>`).join('');
  select.value=(data.cameraPresets||[]).some(p=>p.name===current)?current:(data.activeCameraPreset||'');
  game1CameraDraftStatus(data);
  game1HealthRender();
  game1HealthDraftStatus(data);
  $('save-combat-options').disabled=game1OptionsState.saving;
  $('save-character-life-options').disabled=game1OptionsState.saving;
  for(const id of ['option-camera-save','option-camera-preset-save','option-camera-preset-apply','option-camera-preset-delete','health-ui-save','option-published-debug-save']){
    $(id).disabled=game1OptionsState.saving;
  }
}
async function game1OptionsLoad(){
  try{game1OptionsState.data=await request('/api/options');game1OptionsState.hpDrafts=null;game1OptionsRender()}catch(error){toast(error.message,true)}
}
async function game1OptionsSave(payload,message){
  game1HealthCapture();
  game1OptionsState.saving=true;game1OptionsRender();
  try{game1OptionsState.data=await request('/api/options',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});game1OptionsRender();toast(message)}
  catch(error){toast(error.message,true)}
  finally{game1OptionsState.saving=false;game1OptionsRender()}
}
$('refresh-options').onclick=game1OptionsLoad;
$('save-combat-options').onclick=()=>game1OptionsSave({combat:{stateDurationSeconds:game1OptionNumber('option-combat-state-duration',6)}},'combat options saved');
$('save-character-life-options').onclick=()=>game1OptionsSave({characterAnimations:{deathPlaybackPercent:game1OptionNumber('option-character-death-playback',100),revivePlaybackPercent:game1OptionNumber('option-character-revive-playback',100)}},'character life animation options saved');
$('option-camera-save').onclick=()=>{
  try{const camera=game1CameraRead();game1OptionsSave({camera},'Camera options saved · sync Rojo and restart Play to apply')}
  catch(error){toast(error.message,true)}
};
$('option-camera-draft-import').onclick=()=>{
  const draft=game1OptionsState.data?.cameraDebugDraft;
  if(!draft){toast('No Studio Debug draft received yet',true);return}
  game1CameraFill(draft);
  toast('Studio draft imported into form · click Save to persist');
};
$('option-camera-preset-save').onclick=()=>{
  try{
    const name=$('option-camera-preset-name').value.trim();
    game1OptionsSave({camera:game1CameraRead(),cameraPresetAction:'save',cameraPresetName:name},`Camera preset ${name} saved`);
  }catch(error){toast(error.message,true)}
};
$('option-camera-preset-apply').onclick=()=>{
  const name=$('option-camera-presets').value;
  if(name)game1OptionsSave({cameraPresetAction:'apply',cameraPresetName:name},`Preset ${name} applied to saved Camera Options`);
};
$('option-camera-preset-delete').onclick=()=>{
  const name=$('option-camera-presets').value;
  if(name&&confirm(`Delete camera preset ${name}?`))game1OptionsSave({cameraPresetAction:'delete',cameraPresetName:name},`Preset ${name} deleted`);
};
// Only the transient draft refreshes. Never overwrite form fields under editing.
setInterval(async()=>{
  const panel=$('options-view');
  if(!panel||panel.hidden)return;
  try{
    const data=await request('/api/options');
    const previous=game1OptionsState.data||{};
    game1OptionsState.data={...previous,cameraDebugDraft:data.cameraDebugDraft,cameraDebugDraftAt:data.cameraDebugDraftAt};
    game1OptionsState.data.healthUiDebugDraft=data.healthUiDebugDraft;
    game1OptionsState.data.healthUiDebugDraftAt=data.healthUiDebugDraftAt;
    game1CameraDraftStatus(game1OptionsState.data);
    game1HealthDraftStatus(game1OptionsState.data);
  }catch{}
},2500);
window.game1OptionsLoad=game1OptionsLoad;

// M322: PC and Mobile edit buffers are independent. Save sends only the selected
// profile, preserving the other device's persisted settings.
const GAME1_HP_FIELDS={
  screen:[['enabled','Enabled'],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['textSize','HP digits · px',8,36,1],['top','Top offset · px',0,160,1]],
  self:[['enabled','Show above player'],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['nameSize','Name font · px',8,40,1],['levelSize','Level font · px',8,40,1],['offsetStuds','Above head · studs',0,12,0.25]],
  monster:[['enabled','Show above monsters'],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['nameSize','Name font · px',8,40,1],['levelSize','Level font · px',8,40,1],['offsetStuds','Above head · studs',0,12,0.25]],
  colors:[['green','Green (above 65%)'],['yellow','Yellow (31–65%)'],['red','Red (0–30%)']],
};
function game1HealthEnsureDrafts(){
  if(!game1OptionsState.hpDrafts){
    const data=game1OptionsState.data?.healthUi||{};
    game1OptionsState.hpDrafts=JSON.parse(JSON.stringify(data));
  }
}
function game1HealthCapture(){
  if(!game1OptionsState.hpDrafts)return;
  const current=game1OptionsState.hpDrafts[game1OptionsState.hpDevice];
  if(!current)return;
  for(const [section,fields] of Object.entries(GAME1_HP_FIELDS))for(const [key] of fields){
    const el=document.getElementById(`health-ui-${section}-${key}`);
    if(!el)continue;
    current[section][key]=el.type==='checkbox'?el.checked:
      el.type==='number'?Number(el.value):el.value.trim().toUpperCase();
  }
}
function game1HealthRender(){
  const data=game1OptionsState.data||{};
  game1HealthEnsureDrafts();
  const dev=game1OptionsState.hpDevice;
  const values=game1OptionsState.hpDrafts?.[dev];
  $('health-ui-desktop').classList.toggle('primary',dev==='desktop');
  $('health-ui-mobile').classList.toggle('primary',dev==='mobile');
  $('option-published-debug-buttons').checked=data.debugUi?.[dev]?.showPublishedControls===true;
  if(!values)return;
  const el=$('health-ui-fields');
  el.innerHTML=Object.entries(GAME1_HP_FIELDS).map(([section,fields])=>{
    const title={screen:'01 · Top-screen HP',self:'02 · Your character overhead',monster:'03 · Monster overhead',colors:'04 · Threshold colors'}[section];
    return `<section class="game1-hp-section"><h4>${title}</h4><div class="game1-hp-grid">${fields.map(([key,label,min,max,step])=>{
      const value=values?.[section]?.[key];
      const id=`health-ui-${section}-${key}`;
      if(key==='enabled')return `<label class="game1-hp-enabled"><input type="checkbox" id="${id}" ${value?'checked':''}> ${label}</label>`;
      if(section==='colors')return `<label>${label}<span class="game1-hp-color"><input type="color" id="${id}-picker" value="${esc(value||'#FFFFFF')}"><input id="${id}" type="text" maxlength="7" value="${esc(value||'#FFFFFF')}" pattern="#[0-9A-Fa-f]{6}"></span></label>`;
      return `<label>${label}<input type="number" id="${id}" min="${min}" max="${max}" step="${step}" value="${Number(value)}"></label>`;
    }).join('')}</div></section>`;
  }).join('');
  for(const name of ['green','yellow','red']){
    const input=$(`health-ui-colors-${name}`),picker=$(`health-ui-colors-${name}-picker`);
    picker.oninput=()=>{input.value=picker.value.toUpperCase()};
    input.oninput=()=>{if(/^#[0-9a-f]{6}$/i.test(input.value))picker.value=input.value};
  }
}
function game1HealthValidate(){
  game1HealthCapture();
  const data=game1OptionsState.hpDrafts?.[game1OptionsState.hpDevice];
  if(!data)throw Error('Health profiles not loaded');
  for(const [section,fields] of Object.entries(GAME1_HP_FIELDS))for(const [key,,min,max] of fields){
    const value=data[section][key];
    if(key==='enabled'){if(typeof value!=='boolean')throw Error('Invalid '+section+'.enabled');}
    else if(section==='colors'){
      if(!/^#[a-f0-9]{6}$/i.test(value))throw Error('Invalid RGB hex for '+key);
    }else if(!Number.isFinite(value)||value<min||value>max)throw Error(`${section}.${key}: expected ${min}–${max}`);
  }
  return JSON.parse(JSON.stringify(data));
}
function game1HealthDraftStatus(data){
  const el=$('health-ui-draft-status');if(!el)return;
  const draft=data?.healthUiDebugDraft;
  if(!draft){el.textContent='No Studio HP Debug draft received yet.';return;}
  const clock=new Date((data.healthUiDebugDraftAt||0)*1000).toLocaleTimeString();
  el.textContent=`Studio HP Debug draft (${draft.device.toUpperCase()}) received ${clock}. Import then Save to persist.`;
}
$('health-ui-desktop').onclick=()=>{game1HealthCapture();game1OptionsState.hpDevice='desktop';game1HealthRender()};
$('health-ui-mobile').onclick=()=>{game1HealthCapture();game1OptionsState.hpDevice='mobile';game1HealthRender()};
$('health-ui-save').onclick=()=>{
  try{
    const device=game1OptionsState.hpDevice;
    const settings=game1HealthValidate();
    game1OptionsSave({healthUi:{[device]:settings}},`${device} health UI saved · sync Rojo and restart Play`);
  }catch(error){toast(error.message,true)}
};
$('health-ui-import').onclick=()=>{
  const draft=game1OptionsState.data?.healthUiDebugDraft;
  if(!draft||!draft.device||!draft.settings){toast('No Studio HP Debug draft received yet',true);return}
  game1HealthCapture();
  game1HealthEnsureDrafts();
  game1OptionsState.hpDrafts[draft.device]=JSON.parse(JSON.stringify(draft.settings));
  game1OptionsState.hpDevice=draft.device;
  game1HealthRender();
  toast('Studio HP draft imported. Click Save selected device profile to persist.');
};
$('option-published-debug-save').onclick=()=>{
  const device=game1OptionsState.hpDevice;
  game1OptionsSave({debugUi:{[device]:{showPublishedControls:$('option-published-debug-buttons').checked}}},`${device} published TestPlace debug visibility saved`);
};
