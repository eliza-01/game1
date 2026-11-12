/* M309 · Resource editor for Weapons. Uses the Location Asset dialog shell and
 * the central Atlas Registry editor; publication and Studio Sync stay explicit.
 * New registrations use the collapsed form, existing assets use this dialog. */
window.game1WeaponWorkflow = (() => {
  const shell=window.game1AssetWorkflowDialog;
  const state={slug:'',tab:'identity',busy:false,pendingModel:'',message:'',failed:false};
  const e=v=>esc(String(v??''));
  const find=()=>weaponState.data?.items?.find(v=>v.slug===state.slug);
  const button=(key,text,disabled=false)=>`<button type="button" data-ww-action="${key}" ${disabled?'disabled':''}>${text}</button>`;
  const dialog=()=>shell.ensure('weapon-asset-edit-dialog','Manage Weapon',()=>{
    state.slug='';state.pendingModel='';state.message='';
  });
  function open(slug,tab='identity'){
    const item=weaponState.data?.items?.find(v=>v.slug===slug);
    if(!item)return toast('Weapon not found. Refresh library.',true);
    const d=dialog();if(d.open&&state.slug!==slug)d.close();
    state.slug=slug;state.tab=tab;state.busy=false;state.pendingModel='';state.message='';state.failed=false;
    weaponState.selected=slug;
    weaponRender();render();if(!d.open)d.showModal();
  }
  function notice(message,failed=false){state.message=String(message||'');state.failed=failed;}
  async function run(label,callback){
    if(state.busy)return;
    state.busy=true;notice(`${label}…`);render();
    try{const result=await callback();return result;}
    catch(err){notice(err?.message||String(err),true);return null;}
    finally{state.busy=false;render();}
  }
  function readForm(d){
    const item=find();
    return {
      slug:item.slug,nameEn:d.querySelector('[data-ww-name]').value.trim(),
      nameRu:d.querySelector('[data-ww-name-ru]').value.trim(),
      weaponType:d.querySelector('[data-ww-type]').value,
      rarity:d.querySelector('[data-ww-rarity]').value,
      attackRadiusStuds:Number(d.querySelector('[data-ww-radius]').value),
      statModifiers:{Damage:Number(d.querySelector('[data-ww-damage]').value),
        AttackSpeed:Number(d.querySelector('[data-ww-speed]').value)},
    };
  }
  async function update(payload){
    await request('/api/weapons',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    await weaponLoad();
  }
  function render(){
    const d=document.getElementById('weapon-asset-edit-dialog');if(!d?.open&&!state.slug)return;
    const item=find();if(!d||!item)return;
    const oldScroll=d.querySelector('.real-estate-mesh-dialog-body')?.scrollTop||0;
    const busy=state.busy;
    const modelCurrent=Boolean(item.model_asset_id&&item.model_sha256===item.model_published_sha256);
    const warning=String(item.slug+' '+item.name_en).toLowerCase().includes('bow') && item.weapon_type!=='bow';
    const steps=[{id:'identity',label:'Identity'},{id:'model',label:'Model · FBX'},{id:'atlas',label:'Texture · atlas'}];
    const identities=shell.step('Registration details','Metadata never publishes to Roblox or changes Studio.',
      `<div class="weapon-edit-fields">`+
      `<label>Name EN<input data-ww-name value="${e(item.name_en)}"></label>`+
      `<label>Name RU<input data-ww-name-ru value="${e(item.name_ru)}"></label>`+
      `<label>Type<select data-ww-type>${(weaponState.data?.options?.weaponTypes||[]).map(v=>`<option value="${e(v)}" ${v===item.weapon_type?'selected':''}>${e(v)}</option>`).join('')}</select></label>`+
      `<label>Rarity<select data-ww-rarity>${(weaponState.data?.options?.rarities||[]).map(v=>`<option value="${e(v)}" ${v===item.rarity?'selected':''}>${e(v)}</option>`).join('')}</select></label>`+
      `<label>Attack delta<input data-ww-damage type="number" step="1" value="${e(item.stat_modifiers?.Damage||0)}"></label>`+
      `<label>Attack speed delta<input data-ww-speed type="number" step="1" value="${e(item.stat_modifiers?.AttackSpeed||0)}"></label>`+
      `<label>Range · studs<input data-ww-radius type="number" min="1" max="420" step="0.5" value="${e(item.attack_radius_studs||7)}"></label>`+
      `<label>Stable slug<input value="${e(item.slug)}" readonly></label></div>`+
      (warning?`<p class="weapon-edit-warning">This weapon is registered as <b>${e(item.weapon_type)}</b> although its name suggests a bow. The <b>bow</b> animation set will not be selected until you explicitly change Type and save. Sync Rojo afterward.</p>`:'')+
      `<div class="actions">${button('save','Apply Changes',busy)}${button('startup','Set startup',busy)}${button('unarmed','Unarmed startup',busy)}${button('delete','Delete registration',busy)}</div>`,'Revision '+Number(item.revision||1));
    const models=shell.step('Model · FBX','Model and atlas are independent. Choose a new FBX to register a revision; publish only when changed.',
      `<div class="weapon-asset-status"><strong>Source</strong><small>${e(state.pendingModel||item.model_source_path||'—')}</small>`+
      `<small>Model Asset ID: ${e(item.model_asset_id||'not published')}</small></div>`+
      `<div class="actions">${button('choose','Choose FBX',busy)}${button('save-model','Register FBX revision',busy||!state.pendingModel)}</div>`+
      `<div class="weapon-asset-status"><strong>${modelCurrent?'Model current':'Model publication required'}</strong>`+
      `<small>${modelCurrent?'SHA256 matches published revision.': 'Publishing may create a new Roblox Model Asset ID; no atlas is uploaded.'}</small></div>`+
      `<div class="actions">${button('publish',item.model_asset_id?'Publish changed model':'Publish model',busy||modelCurrent||!weaponState.data?.publication?.configured)}${button('sync','Sync Studio',busy||!item.model_asset_id)}</div>`+
      `<small>Sync Studio is separate and explicit. Changes to registered textures do not publish the model.</small>`,
      modelCurrent?'Published':'Needs publication',modelCurrent?'ready':'pending');
    const legacy=(item.textures||[]).filter(v=>v.asset_id).length&&!item.atlas_binding;
    const texture=shell.step('Texture · atlas','Same published-resolution selector, reviewed replacement and manual Studio Sync as Location Assets.',
      (legacy?`<div class="weapon-edit-warning">Legacy published Image ID. Expected name: <code>&lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png</code>. Use its dot to index without publishing, or choose another atlas.</div>`:'')+
      `<div id="weapon-workflow-atlas" class="game1-asset-atlas-picker"></div>`+
      `<div class="actions">${button('sync','Sync Studio',busy||!item.model_asset_id)}</div>`+
      `<small>Atlas publication and Studio Sync are never automatic.</small>`,item.atlas_binding?'Attached atlas':'Select atlas',item.atlas_binding?'ready':'pending');
    d.innerHTML=`<div class="real-estate-mesh-dialog-head"><div><small>WEAPON · ${e(item.slug)}</small><h3>Manage ${e(item.name_en)}</h3></div><button type="button" data-ww-action="close" aria-label="Close">✕</button></div>`+
      `<div class="real-estate-mesh-dialog-body">${shell.tabs(steps,state.tab,'data-ww-tab')}`+
      `${state.tab==='identity'?identities:state.tab==='model'?models:texture}`+
      `<div class="weapon-asset-status ${state.failed?'issue':''}" role="status" aria-live="polite">${e(state.message||'Changes are saved only by an explicit action.')}</div></div>`;
    d.querySelectorAll('[data-ww-tab]').forEach(b=>b.onclick=()=>{if(state.busy)return;state.tab=b.dataset.wwTab;notice('');render()});
    d.querySelectorAll('[data-ww-action]').forEach(b=>b.onclick=()=>action(b.dataset.wwAction));
    if(state.tab==='atlas')game1WeaponAtlasPicker.render('weapon-workflow-atlas','weapon',item,weaponLoad);
    const body=d.querySelector('.real-estate-mesh-dialog-body');body.scrollTop=oldScroll;
  }
  async function action(key){
    if(key==='close'){if(!state.busy)dialog().close();return;}
    const item=find();if(!item||state.busy)return;
    if(key==='startup')return run('Updating startup weapon',async()=>{
      await request('/api/weapons/'+encodeURIComponent(item.slug)+'/activate',{method:'POST'});
      await weaponLoad();notice(`Startup weapon: ${item.slug}`);
    });
    if(key==='unarmed')return run('Clearing startup weapon',async()=>{
      await request('/api/weapons/active/clear',{method:'POST'});
      await weaponLoad();notice('Startup weapon: unarmed');
    });
    if(key==='delete'){
      if(!confirm(`DELETE the registry record ${item.slug}? Published Cloud assets remain available. This cannot be undone.`))return;
      return run('Deleting registry record',async()=>{
        await request('/api/weapons/'+encodeURIComponent(item.slug),{method:'DELETE'});
        state.slug='';weaponState.selected=null;await weaponLoad();
        dialog().close();toast('Weapon registration removed; Cloud assets preserved.');
      });
    }
    if(key==='choose')return run('Choose FBX',async()=>{
      const result=await request('/api/files/choose-weapon-model',{method:'POST'});
      if(result.path){state.pendingModel=result.path;notice('New FBX selected; register revision before publication.');}
      else notice('Selection cancelled.');
    });
    if(key==='save'){
      const data=readForm(dialog());
      if(!data.nameEn) return notice('Name EN required',true),render();
      if(!Number.isFinite(data.attackRadiusStuds))return notice('Invalid range',true),render();
      return run('Saving identity',async()=>{await update(data);notice('Identity updated. No Roblox publication or Studio Sync performed.');});
    }
    if(key==='save-model')return run('Registering new FBX revision',async()=>{
      if(!state.pendingModel)return;
      await update({slug:item.slug,nameEn:item.name_en,nameRu:item.name_ru,weaponType:item.weapon_type,
        rarity:item.rarity,attackRadiusStuds:item.attack_radius_studs,statModifiers:item.stat_modifiers,
        modelSourcePath:state.pendingModel});
      state.pendingModel='';notice('FBX revision registered. Publish Model explicitly.');
    });
    if(key==='publish'){
      if(!confirm(`Publish changed FBX for ${item.slug}? Atlas publication and Studio Sync stay separate.`))return;
      return run('Publishing Model',async()=>{
        const current=find();if(current.model_asset_id&&current.model_sha256===current.model_published_sha256)throw Error('Model unchanged');
        const result=await request('/api/weapons/'+encodeURIComponent(state.slug)+'/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({includeLegacyTextures:false,description:`Game1 Weapon · ${current.name_en}`})});
        await weaponLoad();notice(`Model published · ${result.model_asset_id}. Sync Studio separately.`);
      });
    }
    if(key==='sync'){
      if(!confirm(`Sync ${state.slug} to connected Studio? This is a separate explicit step.`))return;
      return run('Syncing Studio',async()=>{
        const result=await request('/api/weapons/'+encodeURIComponent(state.slug)+'/sync',{method:'POST'});
        await weaponLoad();notice(`Studio sync finished · ${result.studio?.destination||state.slug}`);
      });
    }
  }
  return Object.freeze({open,render});
})();
