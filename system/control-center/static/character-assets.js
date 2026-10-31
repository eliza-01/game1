const $ = id => document.getElementById(id);
const state = {
  view:'characters', data:null, selected:null, sourcePath:'', autoDisplayName:true,
  animations:null, animationCharacter:'', animationFolder:'', animationFilter:'all', animationSelected:null, lastScan:null, animationPublishing:false,
};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FILENAME_GUIDE_OPEN_KEY='game1.animation.filenameRules.open';
const ANIMATION_FOLDER_KEY='game1.animation.folder';
const ASSET_MANAGER_VIEW_KEY='game1.assetManager.activeSection';
const ASSET_MANAGER_VIEWS=new Set(['characters','animations','animation-speed','weapons','monsters','npcs','locations','location-assets','real-estate','timelines','options']);

function normalizeAnimationFolderPath(value){
  let path=String(value??'').trim();
  if(path.length>=2&&((path.startsWith('"')&&path.endsWith('"'))||(path.startsWith("'")&&path.endsWith("'"))))path=path.slice(1,-1).trim();
  return path;
}
function rememberAnimationFolder(path){try{if(path)localStorage.setItem(ANIMATION_FOLDER_KEY,path);else localStorage.removeItem(ANIMATION_FOLDER_KEY)}catch{}}
function renderAnimationFolderControls(){
  const input=$('animation-folder-path');
  if(input&&document.activeElement!==input&&input.value!==state.animationFolder)input.value=state.animationFolder;
  const scan=$('scan-animations');if(scan)scan.disabled=state.animationPublishing||!state.animationCharacter||!state.animationFolder;
}
function setAnimationFolder(path,persist=true){state.animationFolder=normalizeAnimationFolderPath(path);if(persist)rememberAnimationFolder(state.animationFolder);renderAnimationFolderControls()}
function initAnimationFolderExplorer(){
  const input=$('animation-folder-path');if(!input)return;
  try{state.animationFolder=normalizeAnimationFolderPath(localStorage.getItem(ANIMATION_FOLDER_KEY)||'')}catch{}
  input.value=state.animationFolder;
  input.addEventListener('input',()=>{state.animationFolder=normalizeAnimationFolderPath(input.value);renderAnimationFolderControls()});
  input.addEventListener('change',()=>setAnimationFolder(input.value,true));
  input.addEventListener('keydown',event=>{if(event.key!=='Enter')return;event.preventDefault();setAnimationFolder(input.value,true);if(!$('scan-animations').disabled)scanAnimations()});
  renderAnimationFolderControls();
}
function initFilenameRulesDisclosure(){
  const guide=$('animation-filename-guide');if(!guide)return;
  try{const saved=localStorage.getItem(FILENAME_GUIDE_OPEN_KEY);if(saved!==null)guide.open=saved==='1';}catch{}
  guide.addEventListener('toggle',()=>{try{localStorage.setItem(FILENAME_GUIDE_OPEN_KEY,guide.open?'1':'0')}catch{}});
}

// One global notification surface. Every notice remains visible until the user
// dismisses it or another notice replaces it; no timers, including for errors.
// The third argument is retained for older call sites but no longer changes this policy.
function toast(message,error=false,persistent=false){
  const el=$('toast');
  if(!el)return;
  el.replaceChildren();
  const content=document.createElement('span');
  content.className='toast-message';content.textContent=String(message);
  const close=document.createElement('button');
  close.type='button';close.className='toast-close';close.textContent='×';
  close.setAttribute('aria-label','Dismiss notification');
  close.onclick=()=>{el.className='toast';};
  el.append(content,close);
  el.setAttribute('role',error?'alert':'status');
  el.className='toast show'+(error?' error':'');
}
async function request(url,options){const response=await fetch(url,options);let data={};try{data=await response.json()}catch{}if(!response.ok)throw Error(data.error||`http ${response.status}`);return data}
function selectedRow(){return state.data?.items?.find(x=>x.id===state.selected)||null}
function identityId(){return `${$('race').value}_${$('gender').value}`}
function syncIdentity(){if(state.selected)return;$('character-id').value=identityId();if(state.autoDisplayName)$('display-name').value=`${$('race').value} ${$('gender').value}`}
function statusTag(status){return `<span class="tag ${String(status||'').toLowerCase()}">${esc(status||'')}</span>`}

function setView(view){
  if(!ASSET_MANAGER_VIEWS.has(view))view='characters';
  state.view=view;
  try{localStorage.setItem(ASSET_MANAGER_VIEW_KEY,view)}catch{}
  $('characters-view').hidden=view!=='characters';$('animations-view').hidden=view!=='animations';$('animation-speed-view').hidden=view!=='animation-speed';$('weapons-view').hidden=view!=='weapons';$('monsters-view').hidden=view!=='monsters';$('npcs-view').hidden=view!=='npcs';$('locations-view').hidden=view!=='locations';$('location-assets-view').hidden=view!=='location-assets';$('real-estate-view').hidden=view!=='real-estate';$('timelines-view').hidden=view!=='timelines';$('options-view').hidden=view!=='options';
  $('character-rail').hidden=view!=='characters';$('animation-rail').hidden=view!=='animations';$('weapon-rail').hidden=view!=='weapons';$('monster-rail').hidden=view!=='monsters';$('npc-rail').hidden=view!=='npcs';$('real-estate-rail').hidden=view!=='real-estate';
  $('nav-characters').classList.toggle('active',view==='characters');$('nav-animations').classList.toggle('active',view==='animations');$('nav-animation-speed').classList.toggle('active',view==='animation-speed');$('nav-weapons').classList.toggle('active',view==='weapons');$('nav-monsters').classList.toggle('active',view==='monsters');$('nav-npcs').classList.toggle('active',view==='npcs');$('nav-locations').classList.toggle('active',view==='locations');$('nav-location-assets').classList.toggle('active',view==='location-assets');$('nav-real-estate').classList.toggle('active',view==='real-estate');$('nav-timelines').classList.toggle('active',view==='timelines');$('nav-options').classList.toggle('active',view==='options');
  if(view==='animations')loadAnimations();if(view==='animation-speed'&&window.game1AnimationSpeedLoad)window.game1AnimationSpeedLoad();if(view==='weapons'&&window.game1WeaponsLoad)window.game1WeaponsLoad();if(view==='monsters'&&window.game1MonstersLoad)window.game1MonstersLoad();if(view==='npcs'&&window.game1NpcsLoad)window.game1NpcsLoad();if(view==='locations'&&window.game1LocationsLoad)window.game1LocationsLoad();if(view==='location-assets'&&window.game1LocationAssetsLoad)window.game1LocationAssetsLoad();if(view==='real-estate'&&window.game1RealEstateLoad)window.game1RealEstateLoad();if(view==='timelines'&&window.game1TimelinesLoad)window.game1TimelinesLoad();if(view==='options'&&window.game1OptionsLoad)window.game1OptionsLoad();
}

function characterStatsPayload(){return {Level:Number($('character-stat-level').value||1),MaxHP:Number($('character-stat-hp').value||0),Damage:Number($('character-stat-damage').value||0),Defense:Number($('character-stat-defense').value||0),AttackSpeed:Number($('character-stat-attack-speed').value||0),RunSpeed:Number($('character-stat-run-speed').value||0),CritChance:Number($('character-stat-crit-chance').value||0)}}
function fillCharacterStats(row){const stats=row?.stats||state.data?.options?.defaultStats||{};$('character-stat-level').value=stats.Level??1;$('character-stat-hp').value=stats.MaxHP??100;$('character-stat-damage').value=stats.Damage??10;$('character-stat-defense').value=stats.Defense??0;$('character-stat-attack-speed').value=stats.AttackSpeed??100;$('character-stat-run-speed').value=stats.RunSpeed??50;$('character-stat-crit-chance').value=stats.CritChance??0}
function setForm(row){state.selected=row?.id||null;state.sourcePath='';state.autoDisplayName=!row;if(row){$('race').value=row.race||'human';$('gender').value=row.gender||'female';$('character-id').value=row.id;$('display-name').value=row.display_name||'';$('picked-model').textContent='current model stays active until a replacement is published';}else{$('race').value=state.data?.options?.races?.[0]||'human';$('gender').value=state.data?.options?.genders?.[0]||'female';$('display-name').value='';$('picked-model').textContent='fbx not selected';syncIdentity()}fillCharacterStats(row);game1SyncPublicationDescription("publication-description", "Character Model", row?.display_name || "");renderCharacters()}

function renderRuntime(){const r=state.data.runtime;const host=$('runtime-state');if(r.mode==='assembled'){host.className='runtime-state registered';host.innerHTML=`<strong>assembled · ${esc(r.activeArchetypeId)}</strong><span>${esc(r.race)} / ${esc(r.gender)} · registered component recipe</span>`}else if(r.mode==='registered'){host.className='runtime-state registered';host.innerHTML=`<strong>registered · ${esc(r.activeArchetypeId)}</strong><span>${esc(r.race)} / ${esc(r.gender)} · model asset ${esc(r.modelAssetId)}</span>`}else{host.className='runtime-state bootstrap';host.innerHTML=`<strong>bootstrap placeholder</strong><span>${esc(r.reason)}${r.activeArchetypeId?' · selected '+esc(r.activeArchetypeId):''}</span>`}const pub=state.data.publication||{};$('publication-state').className=pub.configured?'publication-ready':'publication-missing';$('publication-state').textContent=pub.configured?`open cloud: ${pub.creatorType} ${pub.creatorId}`:'open cloud: not configured'}
function openLegacyCharacter(item){
  const panel=document.querySelector('#characters-view .cp-legacy');
  if(panel)panel.open=true;
  setForm(item);
  panel?.scrollIntoView({behavior:'smooth'});
}
function renderTree(){
  const host=$('character-tree');host.replaceChildren();
  for(const mode of ['assembly','model']){
    const items=state.data.items.filter(item=>(item.visual_mode==='assembly'?'assembly':'model')===mode);
    if(!items.length)continue;
    const heading=document.createElement('small');heading.className='character-rail-group';
    heading.textContent=mode==='assembly'?'Modular assemblies':'Legacy whole models';host.append(heading);
    for(const item of items){
      const button=document.createElement('button');button.className=item.id===state.selected?'active':'';
      button.innerHTML=`<span>${esc(item.display_name||item.id)}<small>${esc(item.id)} · ${esc(item.gender||'?')}</small></span><small>${esc(item.status)}</small>`;
      button.onclick=()=>mode==='assembly'?window.game1CharacterAssemblies?.edit(item.id):openLegacyCharacter(item);
      host.append(button);
    }
  }
  if(!state.data.items.length)host.innerHTML='<small class="muted">no registered characters.</small>';
  $('rail-count').textContent=state.data.items.length;
}
function renderRows(){const body=$('rows');body.innerHTML='';for(const item of state.data.items.filter(row=>row.visual_mode!=='assembly')){const active=state.data.activeArchetypeId===item.id;const tr=document.createElement('tr');tr.className=item.id===state.selected?'active':'';tr.innerHTML=`<td>${active?'startup':''}</td><td><b>${esc(item.race||'?')} / ${esc(item.gender||'?')}</b><br><small>${esc(item.id)}</small></td><td>${item.model_asset_id?`asset ${esc(item.model_asset_id)}`:'local only'}<br><small>${esc(item.sha256||'').slice(0,12)}</small></td><td>${esc(item.armature_name||'—')}<br><small>${esc(item.bone_count||0)} bones · ${esc(item.mesh_count||0)} mesh</small></td><td>${statusTag(item.status)}</td><td>${esc(item.revision)}</td><td><div class="row-actions"><button data-open>edit</button><button data-flow>Reg + Publish</button>${active?'<span class=\"cp-published\">✓ startup</span>':'<button data-active>set startup</button>'}<button data-delete class="danger">delete</button></div></td>`;tr.querySelector('[data-open]').onclick=()=>openLegacyCharacter(item);tr.querySelector('[data-flow]').onclick=()=>{setForm(item);window.game1CharacterWorkflow?.publish()};const activateButton=tr.querySelector('[data-active]');if(activateButton){activateButton.disabled=!item.model_asset_id;activateButton.onclick=()=>activate(item.id);}tr.querySelector('[data-delete]').onclick=()=>removeCharacter(item.id);body.appendChild(tr)}}
function renderDetails(row){const host=$('selected-details');if(!row){host.innerHTML='<span class="muted">select a character.</span>';return}host.innerHTML=`<div class="section-title"><div><span>selected</span><h3>${esc(row.display_name)}</h3></div>${statusTag(row.status)}</div><div class="details-grid"><div><b>canonical asset</b><span>${esc(row.source_path||row.prepared_path||'—')}</span></div><div><b>model asset id</b><span>${esc(row.model_asset_id||'not published')}</span></div><div><b>replacement</b><span>${row.model_replacement_pending?'new asset id on next publish':'no pending replacement'}</span></div><div><b>publication</b><span>${esc(row.moderation_state||'—')}</span></div><div><b>armature</b><span>${esc(row.armature_name||'—')} · ${esc(row.bone_count||0)} bones</span></div><div><b>skeleton signature</b><span>${esc(row.skeleton_signature||'—')}</span></div></div>`}
function renderForm(row){const configured=!!state.data?.publication?.configured;const replacement=!!row?.model_replacement_pending;const pending=!!(row&&(!row.model_asset_id||row.status==='CHANGED'||replacement));$('model-status').innerHTML=row?`<strong>${esc(row.display_name)} · ${esc(row.status)}</strong><span>${esc(row.source_path||'no source')} · Roblox asset ${esc(row.model_asset_id||'not published')} · ${esc(row.bone_count||0)} bones</span>`:'<strong>not registered</strong><span>Choose an FBX using Reg + Publish.</span>';const startup=!!row&&state.data.activeArchetypeId===row.id;$('activate-character').hidden=startup;$('activate-character').disabled=startup||!row?.model_asset_id;$('character-startup-badge').hidden=!startup;$('register-character').disabled=!configured;$('register-character').textContent=pending?'Reg + Publish · continue':'Reg + Publish';$('publication-hint').textContent=!configured?'Configure Open Cloud credentials to publish.':replacement?'A registered replacement is pending. Continue to publish it.':row?.model_asset_id?'Current Model Asset ID stays assigned until a replacement is published and committed.':'A single operation registers the FBX, publishes the model and attempts Studio sync.';window.game1CharacterWorkflow?.updateButtons(row)}
function renderCharacters(){if(!state.data)return;const row=selectedRow();const published=state.data.items.filter(x=>x.status==='PUBLISHED').length;$('metric-total').textContent=state.data.items.filter(row=>row.visual_mode!=='assembly').length;$('metric-published').textContent=published;$('metric-active').textContent=state.data.items.some(x=>x.id===state.data.activeArchetypeId&&x.visual_mode!=='assembly')?'1':'0';renderRuntime();renderTree();renderRows();renderDetails(row);renderForm(row)}
async function loadCharacters(){try{const formRace=$('race').value;const formGender=$('gender').value;state.data=await request('/api/characters');const races=state.data.options?.races||['human'];const genders=state.data.options?.genders||['male','female'];$('race').innerHTML=races.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');$('gender').innerHTML=genders.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');if(state.selected&&!state.data.items.some(x=>x.id===state.selected))state.selected=null;let autoSelected=false;if(!state.selected&&state.data.items.length){state.selected=state.data.activeArchetypeId&&state.data.items.some(x=>x.id===state.data.activeArchetypeId&&x.visual_mode!=='assembly')?state.data.activeArchetypeId:state.data.items.find(x=>x.visual_mode!=='assembly')?.id||null;autoSelected=true}const row=selectedRow();const wantedRace=autoSelected?(row?.race||races[0]||''):(formRace||row?.race||races[0]||'');const wantedGender=autoSelected?(row?.gender||genders[0]||''):(formGender||row?.gender||genders[0]||'');$('race').value=races.includes(wantedRace)?wantedRace:(row?.race||races[0]||'');$('gender').value=genders.includes(wantedGender)?wantedGender:(row?.gender||genders[0]||'');if(autoSelected&&row){$('character-id').value=row.id;$('display-name').value=row.display_name||'';fillCharacterStats(row);$('picked-model').textContent='current model stays active until a replacement is published'}else if(!state.selected)syncIdentity();renderCharacters();populateAnimationCharacters()}catch(error){toast(error.message,true)}}
async function chooseModel(){try{const result=await request('/api/files/choose-character-model',{method:'POST'});if(!result.path)return '';state.sourcePath=result.path;$('picked-model').textContent=result.path;return result.path}catch(error){toast(error.message,true);return ''}}
async function registerCharacter(){return window.game1CharacterWorkflow?.publish()}
async function saveCharacterStats(){return window.game1CharacterWorkflow?.saveStats()}
async function saveArchetype(){const row=selectedRow();if(!row)return;try{const oldId=row.id;const nextId=$('character-id').value.trim().toLowerCase();const nextRace=$('race').value;const nextGender=$('gender').value;const identityChanged=oldId!==nextId||row.race!==nextRace||row.gender!==nextGender||$('display-name').value.trim()!==(row.display_name||'');if(identityChanged&&!confirm(`save identity changes for ${oldId}? canonical character and animation paths will be migrated; the currently assigned Roblox model asset id is preserved.`))return;$('save-archetype').disabled=true;toast('saving archetype identity…');const result=await request('/api/characters/'+encodeURIComponent(oldId)+'/identity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:nextId,displayName:$('display-name').value,race:nextRace,gender:nextGender})});state.selected=result.newId;state.animationCharacter=result.newId;await loadCharacters();setForm(selectedRow());toast(`saved ${result.newId}${result.studioSyncRequired?' · sync studio before play':''}`)}catch(error){toast(error.message,true)}finally{renderForm(selectedRow())}}
async function syncStudio(id=state.selected){return window.game1CharacterWorkflow?.retryStudio(id)}
async function activate(id=state.selected){try{if(!id)throw Error('select a character');await request('/api/characters/'+encodeURIComponent(id)+'/activate',{method:'POST'});state.selected=id;await loadCharacters();toast(`active character: ${id}`)}catch(error){toast(error.message,true)}}
async function removeCharacter(id){if(!confirm(`delete ${id} from the game1 character registry? source files are preserved.`))return;try{await request('/api/characters/'+encodeURIComponent(id),{method:'DELETE'});if(state.selected===id)state.selected=null;await loadCharacters();setForm(null);toast(`deleted registry row ${id}`)}catch(error){toast(error.message,true)}}

function populateAnimationCharacters(){
  if(!state.data)return;
  const select=$('animation-character');
  const previous=state.animationCharacter||state.data.activeArchetypeId||state.data.items?.[0]?.id||'';
  select.innerHTML=(state.data.items||[]).map(row=>`<option value="${esc(row.id)}">${esc(row.race)} / ${esc(row.gender)} · ${esc(row.id)}${row.visual_mode==='assembly'?' · сборка':' · legacy'}</option>`).join('');
  if((state.data.items||[]).some(row=>row.id===previous))select.value=previous;
  state.animationCharacter=select.value||'';
}
function animationContext(row){return row.scope==='weapon'?`${row.weapon_set}`:row.scope}
function animationFilterMatch(row){if(state.animationFilter==='all')return true;if(state.animationFilter==='base'||state.animationFilter==='emotions')return row.scope===state.animationFilter;return row.scope==='weapon'&&row.weapon_set===state.animationFilter.replace('weapon:','')}
function renderAnimationTree(){
  const host=$('animation-tree');host.innerHTML='';const data=state.animations||{};const items=data.items||[];const catalog=data.slotCatalog||{};
  const defs=[['all','all clips'],['base','base'],['emotions','emotions'],...(data.weaponSets||[]).map(weapon=>[`weapon:${weapon}`,weapon])];
  if(!defs.some(([id])=>id===state.animationFilter))state.animationFilter='all';
  for(const [id,label] of defs){const rows=id==='all'?items:items.filter(row=>(id==='base'||id==='emotions')?row.scope===id:row.scope==='weapon'&&row.weapon_set===id.split(':')[1]);let meta=`${rows.length} clips`;if(id!=='all'){const expected=(id==='base'||id==='emotions')?(catalog[id]||[]):((catalog.weapon||{})[id.split(':')[1]]||[]);const filled=new Set(rows.map(row=>row.slot)).size;meta=`${filled}/${expected.length} slots · ${rows.length} clips`;}const b=document.createElement('button');b.className=id===state.animationFilter?'active':'';b.innerHTML=`<span>${esc(label)}</span><small>${esc(meta)}</small>`;b.onclick=()=>{state.animationFilter=id;renderAnimations()};host.appendChild(b)}
}
function renderAnimationProfile(){
  const data=state.animations;if(!data)return;const profile=data.profile||{};const char=(data.characters||[]).find(x=>x.id===data.characterId);$('animation-rail-title').textContent=char?`${char.race} / ${char.gender}`:'character';
  const host=$('animation-profile-state');host.className='runtime-state '+(data.skeletonCompatible?'registered':'bootstrap');host.innerHTML=data.characterId?`<strong>${esc(data.characterId)} · ${data.skeletonCompatible?'skeleton compatible':'skeleton changed'}</strong><span>${esc(profile.skeleton_signature||'no skeleton signature')} · scan ${esc(profile.scan_root||'not set')}</span>`:'<strong>no character</strong><span>register a character first.</span>';
  const pub=data.publication||{};$('animation-publication-state').className=pub.configured?'publication-ready':'publication-missing';$('animation-publication-state').textContent=pub.configured?`open cloud: ${pub.creatorType} ${pub.creatorId}`:'open cloud: not configured';
  $('animation-metric-total').textContent=data.summary?.registered||0;$('animation-metric-published').textContent=data.summary?.published||0;$('animation-metric-changed').textContent=data.summary?.changed||0;
}
function renderAnimationRows(){window.game1AnimationUI?.renderRows()}
function renderAnimationDetails(){const host=$('animation-details');const row=(state.animations?.items||[]).find(x=>x.binding_id===state.animationSelected);if(!row){host.innerHTML='<span class="muted">select a clip.</span>';return}host.innerHTML=`<div class="section-title"><div><span>selected clip</span><h3>${esc(row.name)}</h3></div>${statusTag(row.status)}</div><div class="details-grid"><div><b>semantic binding</b><span>${esc(row.scope)} · ${esc(row.weapon_set||'base')} · ${esc(row.slot)} · variant ${esc(row.variant||0)}</span></div><div><b>runtime</b><span>looped ${row.looped?'yes':'no'} · priority ${esc(row.priority)} · playback scaling from Animation Speed</span></div><div><b>canonical asset</b><span>${esc(row.source_path||row.prepared_path)}</span></div><div><b>asset id</b><span>${esc(row.asset_id||'not published')}</span></div><div><b>sha256</b><span>${esc(row.sha256||'')}</span></div><div><b>events</b><span>${esc(row.document?.mode||'legacy clip')} · ${esc(row.document?.events?.length||0)} events${row.document_only?' · no cloud upload':''}</span></div></div>`}
function renderFilenameRules(){window.game1AnimationUI?.renderRules()}
function renderAnimations(){
  renderAnimationFolderControls();if(!state.animations)return;
  renderAnimationProfile();renderFilenameRules();renderAnimationTree();renderAnimationRows();renderAnimationDetails();
  $('animation-table-title').textContent=`${state.animationCharacter||'character'} · animation profile`;
  renderAnimationFolderControls();
}
async function loadAnimations(){try{populateAnimationCharacters();const character=state.animationCharacter||$('animation-character').value||'';state.animations=await request('/api/animations?character='+encodeURIComponent(character));state.animationCharacter=state.animations.characterId||character;if($('animation-character').value!==state.animationCharacter)$('animation-character').value=state.animationCharacter;const profileRoot=normalizeAnimationFolderPath(state.animations.profile?.scan_root||'');if(!state.animationFolder&&profileRoot)setAnimationFolder(profileRoot,true);renderAnimations()}catch(error){toast(error.message,true)}}
async function chooseAnimationFolder(){try{setAnimationFolder($('animation-folder-path').value,false);const result=await request('/api/files/choose-animation-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialPath:state.animationFolder})});if(!result.path)return;setAnimationFolder(result.path,true);renderAnimations()}catch(error){toast(error.message,true)}}
async function scanAnimations(){
  setAnimationFolder($('animation-folder-path').value,true);
  return window.game1AnimationUI?.scanFolder();
}
async function publishAnimation(clipId){try{toast('publishing animation…');await request('/api/animations/'+encodeURIComponent(clipId)+'/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({description:$('animation-publication-description').value})});await loadAnimations();toast('animation published')}catch(error){toast(error.message,true)}}
async function checkRobloxAnimationAssets(){if(state.animationPublishing)return;try{state.animationPublishing=true;renderAnimations();const monsterButton=$('check-roblox-monster-animations');if(monsterButton)monsterButton.disabled=true;toast('checking newer Roblox animation asset versions…');const result=await request('/api/animations/check-roblox-assets',{method:'POST'});await loadAnimations();if(window.game1MonsterAnimationsLoad)await window.game1MonsterAnimationsLoad();const requested=Number(result.requested||0),confirmed=Number(result.confirmed||0),pending=Number(result.pending||0),failed=Number(result.failed||0);if(!requested)toast('Roblox animation check · no CHANGED assets');else toast(`Roblox animation check · confirmed ${confirmed} · pending ${pending} · failed ${failed}`,failed>0)}catch(error){toast(error.message,true)}finally{state.animationPublishing=false;renderAnimations();const monsterButton=$('check-roblox-monster-animations');if(monsterButton)monsterButton.disabled=false}}
window.game1CheckRobloxAnimations=checkRobloxAnimationAssets;
async function setAnimationWeight(bindingId,weight){try{state.animations=await request('/api/animation-bindings/'+encodeURIComponent(bindingId)+'/weight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({weight:Number(weight)})});state.animations.publication=state.data?.publication||{};renderAnimations()}catch(error){toast(error.message,true)}}
async function removeAnimationBinding(bindingId){if(!confirm('Remove this character animation registration? Source files and Roblox Cloud assets are preserved. On the next folder scan it will register as NEW / LOCAL_ONLY (without its old published ID).'))return;try{state.animations=await request('/api/animation-bindings/'+encodeURIComponent(bindingId),{method:'DELETE'});state.animations.publication=state.data?.publication||{};if(state.animationSelected===bindingId)state.animationSelected=null;renderAnimations();toast('animation binding removed')}catch(error){toast(error.message,true)}}

function restoreAssetManagerView(){let saved='characters';try{saved=localStorage.getItem(ASSET_MANAGER_VIEW_KEY)||'characters'}catch{}setView(ASSET_MANAGER_VIEWS.has(saved)?saved:'characters')}
window.addEventListener('load',restoreAssetManagerView);

$('display-name').oninput=()=>{if(!state.selected)state.autoDisplayName=false;window.game1CharacterWorkflow?.updateButtons(selectedRow())};$('character-id').oninput=()=>window.game1CharacterWorkflow?.updateButtons(selectedRow());$('nav-characters').onclick=()=>setView('characters');$('nav-animations').onclick=()=>setView('animations');$('nav-animation-speed').onclick=()=>setView('animation-speed');$('nav-weapons').onclick=()=>setView('weapons');$('nav-monsters').onclick=()=>setView('monsters');$('nav-npcs').onclick=()=>setView('npcs');$('nav-locations').onclick=()=>setView('locations');$('nav-location-assets').onclick=()=>setView('location-assets');$('nav-real-estate').onclick=()=>setView('real-estate');$('nav-timelines').onclick=()=>setView('timelines');$('nav-options').onclick=()=>setView('options');$('race').onchange=()=>{syncIdentity();window.game1CharacterWorkflow?.updateButtons(selectedRow())};$('gender').onchange=()=>{syncIdentity();window.game1CharacterWorkflow?.updateButtons(selectedRow())};$('save-archetype').onclick=saveArchetype;$('save-character-stats').onclick=saveCharacterStats;$('register-character').onclick=registerCharacter;$('activate-character').onclick=()=>activate();$('new-legacy-character').onclick=()=>openLegacyCharacter(null);$('clear-form').onclick=()=>window.game1CharacterWorkflow?.reset();$('refresh').onclick=loadCharacters;$('validate-view').onclick=loadCharacters;$('theme').onclick=()=>document.body.classList.toggle('light');
$('animation-character').onchange=()=>{state.animationCharacter=$('animation-character').value;state.animationSelected=null;state.lastScan=null;loadAnimations()};$('choose-animation-folder').onclick=chooseAnimationFolder;$('scan-animations').onclick=scanAnimations;
initAnimationFolderExplorer();
initFilenameRulesDisclosure();
loadCharacters();

if (typeof game1SyncPublicationDescription === "function" && typeof $("display-name").addEventListener === "function") $("display-name").addEventListener("input", () => game1SyncPublicationDescription("publication-description", "Character Model", $("display-name").value));

window.addEventListener('load',()=>window.game1AnimationUI?.init({
  state:()=>state,render:renderAnimations,load:loadAnimations,request,toast,
  weight:setAnimationWeight,remove:removeAnimationBinding,publish:publishAnimation,
}));
