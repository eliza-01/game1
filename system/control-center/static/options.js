const game1OptionsState={data:null,saving:false};
function game1OptionNumber(id,fallback){const value=Number($(id).value);return Number.isFinite(value)?value:fallback}
function game1OptionsRender(){
  const data=game1OptionsState.data||{};
  const combat=data.combat||{};
  const life=data.characterAnimations||{};
  $('option-combat-state-duration').value=String(combat.stateDurationSeconds??6);
  $('option-character-death-playback').value=String(life.deathPlaybackPercent??100);
  $('option-character-revive-playback').value=String(life.revivePlaybackPercent??100);
  $('save-combat-options').disabled=game1OptionsState.saving;
  $('save-character-life-options').disabled=game1OptionsState.saving;
}
async function game1OptionsLoad(){
  try{game1OptionsState.data=await request('/api/options');game1OptionsRender()}catch(error){toast(error.message,true)}
}
async function game1OptionsSave(payload,message){
  game1OptionsState.saving=true;game1OptionsRender();
  try{game1OptionsState.data=await request('/api/options',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});game1OptionsRender();toast(message)}catch(error){toast(error.message,true)}finally{game1OptionsState.saving=false;game1OptionsRender()}
}
$('refresh-options').onclick=game1OptionsLoad;
$('save-combat-options').onclick=()=>game1OptionsSave({combat:{stateDurationSeconds:game1OptionNumber('option-combat-state-duration',6)}},'combat options saved');
$('save-character-life-options').onclick=()=>game1OptionsSave({characterAnimations:{deathPlaybackPercent:game1OptionNumber('option-character-death-playback',100),revivePlaybackPercent:game1OptionNumber('option-character-revive-playback',100)}},'character life animation options saved');
window.game1OptionsLoad=game1OptionsLoad;
