const game1OptionsState={data:null,saving:false,debugStamp:0,hpDevice:"desktop",hpDrafts:null,uiDevice:"desktop",uiDrafts:null};
const GAME1_CAMERA_FIELDS=[
  ['targetHeight','Target height','studs',0,12,0.25],
  ['distance','Camera distance','studs',4,18,0.25],
  ['pitchDegrees','Start pitch','degrees',-65,60,1],
  ['characterX','Character X','screen',0.2,0.8,0.01],
  ['characterY','Character Y','screen',0.2,0.8,0.01],
  ['cursorX','Aim cursor X','screen',0.1,0.9,0.01],
  ['cursorY','Aim cursor Y','screen',0.1,0.9,0.01],
  ['mobileLookSpeed','Mobile camera look speed','×',0.25,4,0.05],
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
  $('option-monster-return-time').value=String(data.monsterAi?.noDamageReturnSeconds??30);
  game1NpcOverheadRender();
  $('option-character-death-playback').value=String(life.deathPlaybackPercent??100);
  $('option-character-revive-playback').value=String(life.revivePlaybackPercent??100);
  $('option-jump-height').value=String(data.playerJump?.heightMultiplier??2);
  $('option-jump-descent').value=String(data.playerJump?.descentTimeMultiplier??2);
  game1CameraFill(data.camera||{});
  const select=$('option-camera-presets');
  const current=select.value;
  select.innerHTML='<option value="">Choose saved preset…</option>'+(data.cameraPresets||[])
    .map(p=>`<option value="${esc(p.name)}">${esc(p.name)}</option>`).join('');
  select.value=(data.cameraPresets||[]).some(p=>p.name===current)?current:(data.activeCameraPreset||'');
  game1CameraDraftStatus(data);
  game1HealthRender();
  game1HealthDraftStatus(data);
  game1UiRender();
  game1UiDraftStatus(data);
  game1SocketRangesRender();
  game1FloraRender();
  if(typeof game1CreationOptionsRender === "function")game1CreationOptionsRender(data.characterCreation);
  $('option-rotation-windmill-enabled').checked=data.rotations?.windmill_02?.enabled??true;
  $('option-rotation-windmill-period').value=String(data.rotations?.windmill_02?.secondsPerRevolution??3);
  $('option-world-streaming-radius').value=String(data.worldStreaming?.targetRadiusStuds??150);
  $('save-combat-options').disabled=game1OptionsState.saving;
  $('option-npc-overhead-save').disabled=game1OptionsState.saving;
  $('save-character-life-options').disabled=game1OptionsState.saving;
  $('save-player-jump-options').disabled=game1OptionsState.saving;
  for(const id of ['option-camera-save','option-camera-preset-save','option-camera-preset-apply','option-camera-preset-delete','health-ui-save','option-published-debug-save','option-world-streaming-save','option-ui-save','option-sockets-save','option-rotation-save','option-flora-save','option-creation-save']){
    $(id).disabled=game1OptionsState.saving;
  }
}
async function game1OptionsLoad(){
  try{game1OptionsState.data=await request('/api/options');game1OptionsState.hpDrafts=null;game1OptionsState.uiDrafts=null;game1OptionsRender()}catch(error){toast(error.message,true)}
}
async function game1OptionsSave(payload,message){
  game1HealthCapture();
  game1OptionsState.saving=true;game1OptionsRender();
  try{game1OptionsState.data=await request('/api/options',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});game1OptionsRender();toast(message)}
  catch(error){toast(error.message,true)}
  finally{game1OptionsState.saving=false;game1OptionsRender()}
}
// Workspace streaming has one shared target per Place. Command Bar application
// is deliberately explicit: these properties cannot be changed by a client.
function game1WorldStreamingRadius(){
  const input=$('option-world-streaming-radius');
  const radius=Number(input.value);
  if(!Number.isInteger(radius)||radius<96||radius>4096)throw Error('Streaming target must be an integer 96–4096 studs');
  return radius;
}
$('option-world-streaming-save').onclick=()=>{
  try{game1OptionsSave({worldStreaming:{targetRadiusStuds:game1WorldStreamingRadius()}},
    'Streaming target saved · apply in Studio Edit, then Publish to Roblox')}
  catch(error){toast(error.message,true)}
};
$('option-world-streaming-copy').onclick=async()=>{
  try{
    const radius=game1WorldStreamingRadius();
    const command=`-- Eyesland: Roblox Studio Command Bar, EDIT mode. Publish afterward.\n`+
      `local ws = game:GetService("Workspace")\n`+
      `local function set(name, value)\n`+
      `  local ok, err = pcall(function() ws[name] = value end)\n`+
      `  if not ok then warn(name .. ": " .. tostring(err) .. "; set it in Workspace Properties") end\n`+
      `end\n`+
      `set("StreamingEnabled", true)\n`+
      `set("StreamingMinRadius", 64)\n`+
      `set("StreamingTargetRadius", ${radius})\n`+
      `set("ModelStreamingBehavior", Enum.ModelStreamingBehavior.Improved)\n`+
      `set("StreamOutBehavior", Enum.StreamOutBehavior.Opportunistic)\n`+
      `print("Current Workspace target:", ws.StreamingTargetRadius)\n`;
    await navigator.clipboard.writeText(command);
    toast('Studio Command Bar code copied · apply in Edit mode and publish');
  }catch(error){toast(error.message||'Cannot copy Command Bar code',true)}
};
$('refresh-options').onclick=game1OptionsLoad;
$('save-combat-options').onclick=()=>game1OptionsSave({combat:{stateDurationSeconds:game1OptionNumber('option-combat-state-duration',6)},monsterAi:{noDamageReturnSeconds:game1OptionNumber('option-monster-return-time',30)}},'combat and monster return saved');
function game1NpcOverheadRender(){
  const device=$('option-npc-device').value;
  const opts=game1OptionsState.data?.npcOverhead?.[device]||{};
  $('option-npc-name-radius').value=String(opts.nameRadiusStuds??70);
  $('option-npc-health-radius').value=String(opts.healthRadiusStuds??70);
}
$('option-npc-device').onchange=game1NpcOverheadRender;
$('option-npc-overhead-save').onclick=()=>{
  const nameRadiusStuds=game1OptionNumber('option-npc-name-radius',70);
  const healthRadiusStuds=game1OptionNumber('option-npc-health-radius',70);
  if(![nameRadiusStuds,healthRadiusStuds].every(value=>value>=10&&value<=800)){
    toast('NPC distance must be 10–800 studs',true);return;
  }
  const device=$('option-npc-device').value;
  game1OptionsSave({npcOverhead:{[device]:{nameRadiusStuds,healthRadiusStuds}}},'NPC overhead saved');
};
$('save-character-life-options').onclick=()=>game1OptionsSave({characterAnimations:{deathPlaybackPercent:game1OptionNumber('option-character-death-playback',100),revivePlaybackPercent:game1OptionNumber('option-character-revive-playback',100)}},'character life animation options saved');
$('save-player-jump-options').onclick=()=>{
  try {
    const heightMultiplier=game1OptionNumber('option-jump-height',2);
    const descentTimeMultiplier=game1OptionNumber('option-jump-descent',2);
    if(![heightMultiplier,descentTimeMultiplier].every(x=>Number.isFinite(x)&&x>=0.5&&x<=4)) throw Error('Jump multipliers must be 0.5–4');
    game1OptionsSave({playerJump:{heightMultiplier,descentTimeMultiplier}},'Jump settings saved · sync Rojo and restart Play');
  }catch(error){toast(error.message,true)}
};
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
    game1OptionsState.data.uiPresentationDebugDraft=data.uiPresentationDebugDraft;
    game1OptionsState.data.uiPresentationDebugDraftAt=data.uiPresentationDebugDraftAt;
    game1CameraDraftStatus(game1OptionsState.data);
    game1HealthDraftStatus(game1OptionsState.data);
    game1UiDraftStatus(game1OptionsState.data);
  }catch{}
},2500);
window.game1OptionsLoad=game1OptionsLoad;

$('option-rotation-save').onclick=()=>{
  const input=$('option-rotation-windmill-period');
  const period=Number(input.value);
  if(!input.value.trim()||!Number.isFinite(period)||period<0.25||period>120){
    toast('Windmill period must be 0.25–120 seconds',true);return;
  }
  game1OptionsSave({rotations:{windmill_02:{enabled:$('option-rotation-windmill-enabled').checked,secondsPerRevolution:period}}},
    'Windmill rotation saved · sync Rojo and restart Play');
};

// M449 · persisted interaction reach; preview-only Studio HS overrides remain
// separate player attributes. Do not expose non-interactive Bone anchors.
const GAME1_SOCKET_GROUPS = [
  ['house','House sockets',[
    ['door_01_handle_outside_socket','Door · outside'],
    ['door_01_handle_inside_socket','Door · inside'],
    ['door_01_padlock_01_outside_socket','Padlock · outside'],
    ['door_01_padlock_01_inside_socket','Padlock · inside'],
    ['chest_01_socket','Chest'],
    ['elevator_01_socket','Elevator · 1'],
    ['elevator_02_socket','Elevator · 2'],
    ['elevator_03_socket','Elevator · 3'],
    ['fireplace_01_socket','Fireplace'],
  ]],
  ['campfire','Campfire sockets',[
    ['fire_socket','Campfire · fire_socket'],
  ]],
  ['windmill','Windmill sockets',[
    ['windmill_door_handle_socket','Windmill · door handle'],
  ]],
];
function game1SocketRangesRender(){
  const host=$('option-sockets-fields');if(!host)return;
  const ranges=game1OptionsState.data?.socketRanges||{};
  host.innerHTML=GAME1_SOCKET_GROUPS.map(([domain,title,sockets])=>
    `<section class="game1-socket-range-group"><h4>${title}</h4><div class="game1-socket-range-head"><span>Socket</span><span>USE · studs</span><span>AIM · studs</span></div>`+
    sockets.map(([name,label])=>{
      const row=ranges[domain]?.[name]||{};
      const prefix=`option-socket-${domain}-${name}`;
      const input=(field,min,max)=>`<input aria-label="${label} ${field}" id="${prefix}-${field}" type="number" min="${min}" max="${max}" step="0.5" value="${Number(row[field]??(field==='useRadius'?8:4))}" required>`;
      return `<div class="game1-socket-range-row"><label title="${name}">${label}<small>${name}</small></label><label>${input('useRadius',2,30)}</label>`+
        `<label>${row.aimRadius===undefined?'<span class="muted">—</span>':input('aimRadius',1,16)}</label></div>`;
    }).join('')+'</section>').join('');
}
$('option-sockets-save').onclick=()=>{
  try{
    const change={house:{},campfire:{},windmill:{}};
    for(const [domain,,sockets] of GAME1_SOCKET_GROUPS)for(const [name] of sockets){
      const saved=game1OptionsState.data?.socketRanges?.[domain]?.[name];
      if(!saved)throw Error(`Socket settings missing: ${name}. Reload Options.`);
      const values={};
      for(const field of Object.keys(saved)){
        const input=$(`option-socket-${domain}-${name}-${field}`);
        if(!input||!input.value.trim())throw Error(`${name}.${field}: empty value`);
        const value=Number(input.value),low=field==='useRadius'?2:1,high=field==='useRadius'?30:16;
        if(!Number.isFinite(value)||value<low||value>high||value*2!==Math.round(value*2))
          throw Error(`${name}.${field}: ${low}..${high}, step 0.5`);
        values[field]=value;
      }
      if(values.aimRadius!==undefined&&values.aimRadius>values.useRadius)
        throw Error(`${name}: AIM cannot exceed USE`);
      change[domain][name]=values;
    }
    game1OptionsSave({socketRanges:change},'Socket ranges saved · sync Rojo and restart Studio Play');
  }catch(error){toast(error.message,true)}
};

// M322: PC and Mobile edit buffers are independent. Save sends only the selected
// profile, preserving the other device's persisted settings.
const GAME1_HP_FIELDS={
  screen:[['enabled','Enabled'],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['textSize','HP digits · px',8,36,1],['top','Top offset · px',0,160,1]],
  self:[['enabled','Show above player'],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['nameSize','Name font · px',8,40,1],['levelSize','Level font · px',8,40,1],['offsetStuds','Above head · studs',0,12,0.25]],
  monster:[['enabled','Show above monsters'],['maxDistanceStuds','Name + HP visibility radius · studs',20,800,1],['width','Width · px',60,560,1],['height','Height · px',6,60,1],['border','Outline · px',0,8,0.5],['nameSize','Name font · px',8,40,1],['levelSize','Level font · px',8,40,1],['offsetStuds','Above head · studs',0,12,0.25]],
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

// M443 · editable device buffers; saving one does not overwrite the other.
const GAME1_UI_FIELDS = {
  interaction: [['offsetXPx','Horizontal offset · px',-500,500,1],['offsetYPx','Vertical offset · px',-500,500,1],['widthPx','Window width · px',180,450,1],['fontPx','Button font · px',10,36,1]],
  status: [['offsetXPx','Horizontal offset · px',-500,500,1],['offsetYPx','Vertical offset · px',-500,500,1],['titleFontPx','Title font · px',10,36,1],['labelFontPx','Row font · px',10,36,1],['timerFontPx','Timer font · px',9,36,1]],
  notification: [['offsetXPx','Horizontal offset · px',-500,500,1],['offsetYPx','Vertical offset · px',-500,500,1],['fontPx','Message font · px',10,36,1],['paddingPx','Box padding · px',0,24,1],['durationSeconds','Hide after · sec',0.2,15,0.1]],
  resource: [['offsetXPx','Horizontal offset · px',-500,500,1],['offsetYPx','Vertical offset · px',-500,500,1],['fontPx','Resource font · px',10,36,1],['paddingPx','Box padding · px',0,24,1],['risePx','Float distance · px',0,200,1],['durationSeconds','Fade time · sec',0.2,15,0.1]],
};
function game1UiEnsure(){
  if(!game1OptionsState.uiDrafts)game1OptionsState.uiDrafts=JSON.parse(JSON.stringify(game1OptionsState.data?.uiPresentation||{}));
}
function game1UiCapture(){
  if(!game1OptionsState.uiDrafts)return;
  const profile=game1OptionsState.uiDrafts[game1OptionsState.uiDevice];if(!profile)return;
  for(const [group,fields] of Object.entries(GAME1_UI_FIELDS))for(const [key] of fields){
    const input=$(`option-ui-${group}-${key}`);
    if(input)profile[group][key]=Number(input.value);
  }
}
function game1UiRender(){
  game1UiEnsure();
  const device=game1OptionsState.uiDevice;
  $('option-ui-desktop').classList.toggle('primary',device==='desktop');
  $('option-ui-mobile').classList.toggle('primary',device==='mobile');
  const profile=game1OptionsState.uiDrafts?.[device];if(!profile)return;
  $('option-ui-fields').innerHTML=Object.entries(GAME1_UI_FIELDS).map(([group,fields])=>
    `<section class="game1-ui-group"><h4>${({interaction:'01 · Interaction window',status:'02 · Fire & cooking status',notification:'03 · Notifications / transitions',resource:'04 · Resource gain / spending'}[group])}</h4>`+
    fields.map(([key,label,min,max,step])=>`<label>${label}<input type="number" id="option-ui-${group}-${key}" min="${min}" max="${max}" step="${step}" value="${Number(profile[group]?.[key]??0)}"></label>`).join('')+'</section>').join('');
}
function game1UiRead(){
  game1UiCapture();
  const profile=game1OptionsState.uiDrafts?.[game1OptionsState.uiDevice];
  if(!profile)throw Error('UI profile unavailable');
  for(const [group,fields] of Object.entries(GAME1_UI_FIELDS))for(const [key,,min,max] of fields){
    const val=profile[group][key];
    if(!Number.isFinite(val)||val<min||val>max||(!key.endsWith('Seconds')&&!Number.isInteger(val)))
      throw Error(`${group}.${key}: expected ${min}..${max}`);
  }
  return JSON.parse(JSON.stringify(profile));
}
function game1UiDraftStatus(data){
  const el=$('option-ui-draft-status');if(!el)return;
  const draft=data?.uiPresentationDebugDraft;
  el.textContent=draft?`Studio UI Debug (${draft.device}) · ${new Date((data.uiPresentationDebugDraftAt||0)*1000).toLocaleTimeString()} · Import then Save`:'No Studio UI draft yet.';
}
$('option-ui-desktop').onclick=()=>{game1UiCapture();game1OptionsState.uiDevice='desktop';game1UiRender()};
$('option-ui-mobile').onclick=()=>{game1UiCapture();game1OptionsState.uiDevice='mobile';game1UiRender()};
$('option-ui-save').onclick=()=>{
  try{const device=game1OptionsState.uiDevice;game1OptionsSave({uiPresentation:{[device]:game1UiRead()}},`${device} UI settings saved · sync Rojo and restart Play`)}catch(e){toast(e.message,true)}
};
$('option-ui-import').onclick=()=>{
  const draft=game1OptionsState.data?.uiPresentationDebugDraft;
  if(!draft){toast('No Studio UI draft received yet',true);return;}
  game1UiCapture();game1UiEnsure();
  game1OptionsState.uiDrafts[draft.device]=JSON.parse(JSON.stringify(draft.settings));
  game1OptionsState.uiDevice=draft.device;
  game1UiRender();toast('Studio UI draft imported · Save to persist');
};

// M456 · Flora is a purely client-side visual effect. Saved values are emitted
// in GameOptionsRegistry; no server mechanics or per-player remotes are changed.
const GAME1_FLORA_FIELDS=['leavesPerBurst','spawnRadiusStuds','spreadRadiusStuds',
  'contactPaddingStuds','durationSeconds','cooldownSeconds','maxActiveLeaves'];
const GAME1_FLORA_BOUNDS={leavesPerBurst:[1,20],spawnRadiusStuds:[0,8],
  spreadRadiusStuds:[0.5,20],contactPaddingStuds:[0,5],durationSeconds:[0.3,4],
  cooldownSeconds:[0.2,30],maxActiveLeaves:[8,96]};
function game1FloraRender(){
  const flora=game1OptionsState.data?.flora||{};
  $('option-flora-enabled').checked=flora.enabled??true;
  $('option-flora-leafAssetSlug').value=flora.leafAssetSlug??'leaf_01';
  $('option-flora-residentAssets').value=(flora.residentAssets||['leaf_01']).join(', ');
  for(const key of GAME1_FLORA_FIELDS){
    if(flora[key]!==undefined)$('option-flora-'+key).value=String(flora[key]);
  }
}
$('option-flora-save').onclick=()=>{
  try{
    const flora={enabled:$('option-flora-enabled').checked,
      leafAssetSlug:$('option-flora-leafAssetSlug').value.trim(),
      residentAssets:$('option-flora-residentAssets').value.split(',').map(s=>s.trim()).filter(Boolean)};
    if(flora.residentAssets.length<1||flora.residentAssets.length>8||
      new Set(flora.residentAssets).size!==flora.residentAssets.length ||
      !flora.residentAssets.includes(flora.leafAssetSlug))throw Error('Resident assets: 1–8 unique slugs, including leaf slug');
    for(const key of GAME1_FLORA_FIELDS){
      const el=$('option-flora-'+key),value=Number(el.value),[lo,hi]=GAME1_FLORA_BOUNDS[key];
      if(!el.value.trim()||!Number.isFinite(value)||value<lo||value>hi ||
        (['leavesPerBurst','maxActiveLeaves'].includes(key)&&!Number.isInteger(value)))
        throw Error(`Flora ${key}: expected ${lo}–${hi}`);
      flora[key]=value;
    }
    if(flora.leavesPerBurst>flora.maxActiveLeaves)throw Error('Max active must cover one full burst');
    game1OptionsSave({flora},'Flora settings saved · Rojo Sync and restart Play');
  }catch(error){toast(error.message,true)}
};
