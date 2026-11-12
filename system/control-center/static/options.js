const game1OptionsState={data:null,saving:false,debugStamp:0};
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
  $('save-combat-options').disabled=game1OptionsState.saving;
  $('save-character-life-options').disabled=game1OptionsState.saving;
  for(const id of ['option-camera-save','option-camera-preset-save','option-camera-preset-apply','option-camera-preset-delete']){
    $(id).disabled=game1OptionsState.saving;
  }
}
async function game1OptionsLoad(){
  try{game1OptionsState.data=await request('/api/options');game1OptionsRender()}catch(error){toast(error.message,true)}
}
async function game1OptionsSave(payload,message){
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
    game1CameraDraftStatus(game1OptionsState.data);
  }catch{}
},2500);
window.game1OptionsLoad=game1OptionsLoad;
