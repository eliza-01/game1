/* Bow ammunition catalog, within Weapons. Runtime reads only the generated ArrowRegistry. */
const arrowState={items:[],selected:'',modelPath:'',texturePath:''};
const arrowGet=()=>arrowState.items.find(row=>row.slug===arrowState.selected);
const arrowEsc=value=>esc(value??'');
async function arrowLoad(){
  try{
    const data=await request('/api/arrows');
    arrowState.items=data.items||[];
    await game1WeaponAtlasPicker.refresh();
    if(arrowState.selected&&!arrowState.items.some(a=>a.slug===arrowState.selected))arrowState.selected='';
    const select=$('arrow-active');
    select.innerHTML='<option value="">No published arrow (procedural fallback)</option>'+
      arrowState.items.filter(row=>row.status==='PUBLISHED').map(row=>`<option value="${arrowEsc(row.slug)}">${arrowEsc(row.name)} · ${arrowEsc(row.speed)} studs/s</option>`).join('');
    select.value=data.activeArrowSlug||'';
    arrowRender();
    if(arrowState.selected)game1WeaponAtlasPicker.render('arrow-atlas-picker','arrow',arrowGet(),arrowLoad);
  }catch(error){toast(error.message,true)}
}
function arrowRender(){
  const host=$('arrow-rows');host.innerHTML='';
  for(const row of arrowState.items){
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${arrowEsc(row.name)}<small> · ${arrowEsc(row.slug)}</small></td><td>${arrowEsc(row.speed)} studs/s</td><td>${arrowEsc(row.status)}</td><td>${arrowEsc(row.model_asset_id||'local')}</td><td><div data-arrow-atlas-preview>${game1WeaponAtlasPicker.summary('arrow',row)}</div>${!row.atlas_binding&&row.texture_asset_id?'<small class="deco-atlas-warning">⚠ Legacy atlas</small>':''}</td><td><button data-edit>edit</button> <button data-publish ${row.model_asset_id&&row.sha256===row.published_sha256?'disabled':''}>publish model</button> <button data-sync ${row.status!=='PUBLISHED'?'disabled':''}>sync studio</button></td>`;
    tr.querySelector('[data-edit]').onclick=()=>arrowSelect(row.slug);
    tr.querySelectorAll('[data-atlas-preview]').forEach(dot=>dot.onclick=()=>{
      arrowSelect(row.slug);
      $('arrow-atlas-picker').scrollIntoView({behavior:'smooth',block:'center'});
    });
    tr.querySelector('[data-publish]').onclick=()=>arrowPublish(row.slug);
    tr.querySelector('[data-sync]').onclick=()=>arrowSync(row.slug);
    host.appendChild(tr);
  }
  if(!arrowState.items.length)host.innerHTML='<tr><td colspan="6">No arrows registered yet.</td></tr>';
}
function arrowSelect(slug){
  arrowState.selected=slug||'';arrowState.modelPath='';arrowState.texturePath='';
  const row=arrowGet();
  $('arrow-name').value=row?.name||'';
  $('arrow-slug').value=row?.slug||'';
  $('arrow-speed').value=String(row?.speed||145);
  $('arrow-axis').value=row?.forward_axis||'-Z';
  $('arrow-penetration').value=String(row?.penetration_studs??0.12);
  game1WeaponAtlasPicker.render('arrow-atlas-picker','arrow',row,arrowLoad);
  $('arrow-model-file').textContent=row?.source_path||'choose FBX';
  $('arrow-texture-file').textContent=row?.texture_path||'optional PNG/JPG';
}
async function arrowPickModel(){try{const result=await request('/api/files/choose-weapon-model',{method:'POST'});if(result.path){arrowState.modelPath=result.path;$('arrow-model-file').textContent=result.path}}catch(e){toast(e.message,true)}}
async function arrowPickTexture(){try{const result=await request('/api/files/choose-weapon-textures',{method:'POST'});if((result.paths||[]).length){arrowState.texturePath=result.paths[0];$('arrow-texture-file').textContent=result.paths[0]}}catch(e){toast(e.message,true)}}
async function arrowSave(){
  try{
    const slug=arrowState.selected||weaponSlugify($('arrow-name').value);
    const result=await request('/api/arrows',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({slug,name:$('arrow-name').value.trim(),speed:Number($('arrow-speed').value),
        forwardAxis:$('arrow-axis').value,penetrationStuds:Number($('arrow-penetration').value),modelSourcePath:arrowState.modelPath,textureSourcePath:arrowState.texturePath})});
    arrowState.selected=result.slug;await arrowLoad();arrowSelect(result.slug);toast('arrow saved');
  }catch(e){toast(e.message,true)}
}
async function arrowPublish(slug){
  const item=arrowState.items.find(row=>row.slug===slug);
  if(!item)return;
  const changed=!item.model_asset_id||item.sha256!==item.published_sha256;
  if(!changed){$('arrow-operation-status').textContent='Arrow Model unchanged. Atlas is published in the shared editor.';return;}
  if(!confirm(`${item.model_asset_id?'Replace Model '+item.model_asset_id:'Create Model ID'} for arrow ${slug}? Only FBX; atlas and Studio Sync are explicit separate actions.`))return;
  const status=$('arrow-operation-status');
  try{
    status.textContent=`${slug}: publishing changed arrow FBX through Open Cloud…`;
    const result=await request('/api/arrows/'+encodeURIComponent(slug)+'/publish',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        includeLegacyTextures:false,description:'Game1 Arrow '+slug})});
    await arrowLoad();status.textContent=`Arrow ${slug}: Model ID ${result.model_asset_id} ready. Sync Studio separately.`;
  }catch(e){status.textContent=`Arrow Model publication failed: ${e.message}`;toast(e.message,true)}
}
async function arrowSync(slug){try{
  if(!confirm(`Sync published arrow ${slug} into ServerStorage in the connected Roblox Studio?`))return;
  $('arrow-operation-status').textContent=`Syncing ${slug} · Studio Bridge…`;
  await request('/api/arrows/'+encodeURIComponent(slug)+'/sync',{method:'POST'});$('arrow-operation-status').textContent=`${slug} synced to ServerStorage`;toast('arrow template synced to ServerStorage')}catch(e){toast(e.message,true)}}
async function arrowActivate(){try{await request('/api/arrows/'+encodeURIComponent($('arrow-active').value)+'/activate',{method:'POST'});await arrowLoad();toast('active arrow updated; sync Rojo')}catch(e){toast(e.message,true)}}
$('arrow-new').onclick=()=>arrowSelect('');
$('arrow-pick-model').onclick=arrowPickModel;
$('arrow-pick-texture').onclick=arrowPickTexture;
$('arrow-save').onclick=arrowSave;
$('arrow-use').onclick=arrowActivate;
const priorWeaponLoad=window.game1WeaponsLoad;
window.game1WeaponsLoad=async function(){await priorWeaponLoad?.();await arrowLoad()};
