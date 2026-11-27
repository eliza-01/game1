/* Database authoring: stable item IDs, explicit model bindings, revision guarded save. */
(() => {
  let snapshot=null, tab='monsters', busy=false, dirty=false;
  const gradeNames=['Newbie','D','C','B','A','S','SS','SSS'];
  window.game1EquipmentGrade=level=>{const band=Math.max(0,Math.min(7,Math.floor(level/10)));return {name:gradeNames[band]+(level%10>=5?'+':''),required:Math.max(1,band*10)}};
  const groups={monsters:'Monsters',skills:'Skills',weapons:'Weapons',levels:'Levels',rules:'Character',armor:'Armor',bindings:'Model bindings',spawnZones:'Spawn Zones',rescueRoutes:'Rescue Routes'};
  const fields={levels:['level','hp','attackBonus','xpNext'],weapons:['id','type','level','damage','price','attackSpeedDelta','critChance','radius','arc','rarity','upgradePrice'],armor:['id','level','hp','price'],monsters:['id','nameEn','nameRu','type','level','hp','damage','critChance','xp','gold','attackRange','attackSpeed','runSpeed','aggroRadiusStuds','aggressive','deathChase']};
  const names={nameEn:'EN',nameRu:'RU',aggroRadiusStuds:'Aggro · studs',aggressive:'Aggressive',deathChase:'Death Chase',runSpeed:'RunSpeed · /10 studs/s',attackSpeed:'ASPD',attackRange:'Range · studs',level:'LVL',hp:'HP',attackBonus:'Level ATK bonus',xpNext:'XP → next',damage:'ATK bonus',price:'Price',attackSpeedDelta:'ASPD Δ',critChance:'Crit %',radius:'Radius',arc:'Arc °',rarity:'Rarity',upgradePrice:'Upgrade cost',xp:'XP',gold:'Gold',id:'ID',type:'Type'};
  const labels={weapon:'Оружие',armor:'Броня',monster:'Монстр'};
  const label=id=>{const [kind,n]=id.split('_');return `${labels[kind]||kind}_${n}`};
  const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el};
  const status=(message)=>{$('balance-status').textContent=message;};
  const change=()=>{for(const row of snapshot?.balance?.weapons||[]){if(!row.recipe)continue;const source=snapshot.balance.weapons.find(w=>w.id===row.recipe.swordId);row.price=source?.price==null||row.recipe.fee==null?null:2*source.price+row.recipe.fee;const cell=document.querySelector(`[data-recipe-cost="${row.id}"]`);if(cell)cell.textContent=row.price??'—'}dirty=true;$('balance-save').disabled=busy||!snapshot;status('Unsaved changes');};
  function select(values,current,onChange){const el=node('select');for(const [value,text] of values){const option=node('option',text);option.value=value;el.append(option)}el.value=current;el.onchange=()=>onChange(el.value);return el}
  function number(value,apply){const el=node('input');el.type='number';el.step='any';el.value=value;el.style.minWidth='64px';el.style.width='88px';el.oninput=()=>{apply(el.value===''?null:Number(el.value));change()};return el}
  function table(headers){const t=node('table'),head=node('thead'),tr=node('tr'),body=node('tbody');for(const h of headers)tr.append(node('th',h));head.append(tr);t.append(head,body);$('balance-content').append(t);return body}
  function cell(tr,content){const td=node('td');if(typeof content==='string')td.textContent=content;else td.append(content);tr.append(td)}
  function bindingTable(kind,models,bindings,rows){
    const body=table([kind,'Balance ID']);
    const all=new Map(models.map(model=>[model.slug,model]));for(const slug of Object.keys(bindings))if(!all.has(slug))all.set(slug,{slug});
    for(const model of all.values()){
      const tr=node('tr');cell(tr,model.slug);const options=[['','—']];
      for(const r of rows)if(kind==='Monster model'||r.type===model.type)options.push([r.id,`${r.nameEn||label(r.id)} · ${r.type} · LVL ${r.level}`]);
      if(bindings[model.slug]&&!options.some(v=>v[0]===bindings[model.slug]))options.push([bindings[model.slug],`${label(bindings[model.slug])} · incompatible / retired`]);
      cell(tr,select(options,bindings[model.slug]||'',value=>{if(value)bindings[model.slug]=value;else delete bindings[model.slug];change()}));body.append(tr);
    }
  }
  function applySearch(){const q=$('balance-search').value.trim().toLocaleLowerCase();for(const tr of $('balance-content').querySelectorAll('tbody tr')){const values=[tr.textContent,...Array.from(tr.querySelectorAll('input,select'),el=>el.value),tr.dataset.identity||''];tr.hidden=!!q&&!values.join(' ').toLocaleLowerCase().includes(q)}}
  $('balance-search').oninput=applySearch;
  function speciesEdit(row,key,value,body){const group=row.nameEn? snapshot.balance.monsters.filter(r=>r.nameEn===row.nameEn):[row];for(const r of group){r[key]=value;const input=body.querySelector(`[data-row="${r.id}"][data-field="${key}"]`);if(input){if(key==='aggressive'||key==='deathChase')input.checked=value;else if(document.activeElement!==input)input.value=value??''}}change()}
  let spawnLoadToken=0, spawnData=null;
  const spawnChanges=new Map();
  const hasChanges=()=>dirty||spawnChanges.size>0;
  function spawnChange(r,key,value,tr){
    const entry=spawnChanges.get(r.spawnId)||{spawnId:r.spawnId,expectedUpdatedAtUtc:r.updatedAtUtc??null,changes:{}};
    if(value===r[key])delete entry.changes[key];else entry.changes[key]=value;
    if(Object.keys(entry.changes).length)spawnChanges.set(r.spawnId,entry);else spawnChanges.delete(r.spawnId);
    tr.classList.toggle('spawn-dirty',spawnChanges.has(r.spawnId));
    $('balance-save').disabled=busy||!hasChanges();status(hasChanges()?'Unsaved changes':'Ready');
  }
  function drawSpawnZones(){
    if(!spawnData)return;
    const content=$('balance-content');content.replaceChildren();
    const note=node('p','Edit parameters here. Create, move or delete zones in Studio → Monster Spawns. Rojo Sync before Play.');note.className='spawn-note';content.append(note);
    const body=table(['Monster · LVL','Place / map','Position · studs','Radius','Count','Aggressive','Aggro · studs','Pursuit mode','Home leash','Respawn · s','Enabled','Status']);
    body.parentElement.className='spawn-zone-table';
    const choices=spawnData.species.flatMap(g=>g.levels.map(l=>[l.id,`${g.nameEn||g.key} · Lv.${l.level} · ${l.type}`]));
    for(const r of spawnData.records){
      const tr=node('tr');tr.dataset.identity=r.spawnId;tr.title=r.spawnId;
      const patch=spawnChanges.get(r.spawnId)?.changes||{}, draft={...r,...patch};
      tr.classList.toggle('spawn-dirty',spawnChanges.has(r.spawnId));
      const set=(key,value)=>{draft[key]=value;spawnChange(r,key,value,tr)};
      const opts=r.balanceId?choices:[['',`${r.monsterName||r.monster?.name} · Lv.${r.level??'?'} · legacy`],...choices];
      cell(tr,select(opts,draft.balanceId||'',v=>set('balanceId',v||r.balanceId)));
      cell(tr,`${r.placeId} / ${r.mapKey}`);
      const p=r.position||{};const pos=node('span',[p.x,p.y,p.z].map(v=>Number.isFinite(v)?Number(v.toFixed(2)):'—').join(', '));pos.title=`${p.x}, ${p.y}, ${p.z}`;cell(tr,pos);
      const numeric=(key,min,max,step,label)=>{const el=node('input');el.type='number';el.min=min;el.max=max;el.step=step;el.value=draft[key]??'';el.setAttribute('aria-label',label);el.oninput=()=>set(key,el.value===''?null:Number(el.value));return el};
      const check=(key,label)=>{const el=node('input');el.type='checkbox';el.checked=!!draft[key];el.setAttribute('aria-label',label);el.onchange=()=>set(key,el.checked);return el};
      cell(tr,numeric('spawnRadius',0,10000,'any','Spawn radius'));cell(tr,numeric('maxAlive',1,1000,1,'Monster count'));
      cell(tr,check('aggressive','Aggressive'));cell(tr,numeric('aggroRadiusStuds',0,10000,'any','Aggro radius'));
      const leash=numeric('homeRadiusStuds',1,10000,'any','Home leash');const dash=node('span','—');
      const mode=select([['home','Home Leash'],['death','Death Chase']],draft.deathChase?'death':'home',v=>{set('deathChase',v==='death');leash.hidden=draft.deathChase;dash.hidden=!draft.deathChase;leash.disabled=draft.deathChase});
      leash.hidden=draft.deathChase;leash.disabled=draft.deathChase;dash.hidden=!draft.deathChase;cell(tr,mode);const holder=node('span');holder.append(leash,dash);cell(tr,holder);
      cell(tr,numeric('respawnSeconds',0,86400,'any','Respawn seconds'));cell(tr,check('enabled','Enabled'));
      const changedModel=draft.balanceId!==r.balanceId;const ready=node('span',!draft.enabled?'Disabled':changedModel?'Save to check':r.readiness?.ready?'Ready':'Model pending');ready.className='tag';cell(tr,ready);body.append(tr);
    }
    if(!spawnData.records.length)content.append(node('p','No saved zones.'));
    applySearch();
  }
  async function renderSpawnZones(){
    if(spawnChanges.size&&spawnData){drawSpawnZones();return}
    const token=++spawnLoadToken;
    try{
      const data=await request('/api/monster-spawns/catalog');
      if(token!==spawnLoadToken||tab!=='spawnZones'||busy||spawnChanges.size)return;
      if($('balance-content').contains(document.activeElement))return;
      const same=JSON.stringify(data)===JSON.stringify(spawnData);spawnData=data;
      if((!same||!$('balance-content').querySelector('.spawn-zone-table'))&&!$('balance-content').contains(document.activeElement))drawSpawnZones();
    }catch(e){if(token===spawnLoadToken&&tab==='spawnZones')status(e.message)}
  }
  let rescueLoadToken=0;
  async function renderRescueRoutes(){
    const token=++rescueLoadToken;
    try{
      const data=await request('/api/rescue-routes');
      if(token!==rescueLoadToken||tab!=='rescueRoutes')return;
      $('balance-content').replaceChildren();
      $('balance-content').append(node('p','Studio → game1 → Rescue Routes. Read-only mirror of last synchronized Place.'));
      const body=table(['Place','Map ID','Catalog','Name','Route ID','Points','Length · studs']);
      for(const [id,map] of Object.entries(data.maps||{}))for(const route of map.routes){
        const tr=node('tr');tr.dataset.identity=route.id;
        for(const value of [map.placeId,map.mapId||id,route.catalog||'Unsorted',route.name||route.id,route.id,route.points.length,route.lengthStuds])cell(tr,String(value));
        body.append(tr);
      }
      if(!body.rows.length)$('balance-content').append(node('p','No synchronized routes.'));
      applySearch();
    }catch(e){if(token===rescueLoadToken&&tab==='rescueRoutes')$('balance-content').replaceChildren(node('p',e.message))}
  }
  // Poll only clean, unfocused zones; never replace an active editor.
  setInterval(()=>{if($('database-view').hidden||$('balance-panel').hidden)return;if(tab==='spawnZones'&&!busy&&!spawnChanges.size&&!$('balance-content').contains(document.activeElement))renderSpawnZones();if(tab==='rescueRoutes')renderRescueRoutes()},3000);
  function render(){
    $('balance-tabs').replaceChildren();$('balance-content').replaceChildren();$('balance-save').disabled=busy||!snapshot||!hasChanges();
    for(const [key,title] of Object.entries(groups)){const b=node('button',title);b.type='button';b.className=key===tab?'primary':'';b.onclick=()=>{tab=key;$('balance-search').value='';render()};$('balance-tabs').append(b)}
    $('balance-movement-disclosure').hidden=tab!=='weapons';
    if(!snapshot)return;
    queueMicrotask(applySearch);
    if(tab==='spawnZones'){if(spawnData)drawSpawnZones();renderSpawnZones();return;}
    if(tab==='rescueRoutes'){renderRescueRoutes();return;}
    if(tab==='skills'){window.game1RenderSkills($('balance-content'),snapshot,change,applySearch);return;}
    const d=snapshot.balance;
    if(tab==='rules'){
      const body=table(['Parameter','Value']);for(const [key,val] of Object.entries(d.rules)){const tr=node('tr');cell(tr,({baseRunSpeed:'RunSpeed · /10 studs/s',monsterCastSeconds:'Special cast · s',critChance:'Unarmed crit %',maxCritChance:'Max crit %',critMultiplier:'Crit damage ×'}[key]||key));cell(tr,number(val,v=>d.rules[key]=v));body.append(tr)}return;
    }
    if(tab==='bindings'){
      bindingTable('Weapon model',snapshot.weaponModels,d.weaponBindings,d.weapons);
      bindingTable('Monster model',snapshot.monsterModels,d.monsterBindings,d.monsters);return;
    }
    const columns=tab==='monsters'?window.game1MonsterTable.columns(fields[tab]):fields[tab], headers=columns.map(k=>tab==='monsters'&&k==='damage'?'Damage':names[k]);if(tab==='levels')headers.push('Total XP');if(tab==='weapons')headers.push('Grade · required LVL','ATK +0 / max','Craft recipe · fee');
    const body=table(headers);let total=0;
    if(tab==='monsters')window.game1MonsterTable.decorate(body.parentElement.tHead.rows[0],columns,render);
    const rows=tab==='monsters'?window.game1MonsterTable.rows(d.monsters):tab==='weapons'?[...d[tab]].sort((a,b)=>a.level-b.level||a.id.localeCompare(b.id)):d[tab];
    for(const row of rows){const tr=node('tr');tr.dataset.identity=row.id||'';let derived,gradeCell;
      function updateDerived(){if(gradeCell){const g=window.game1EquipmentGrade(row.level);gradeCell.textContent=`${g.name} · ${g.required}`}if(tab==='weapons'&&derived)derived.textContent=`${d.rules.baseDamage+d.levels[row.level-1].attackBonus+row.damage} / ${d.rules.baseDamage+d.levels[row.level-1].attackBonus+Math.round(row.damage*(1+d.rules.maxUpgrade*d.rules.upgradePercent/100))}`}
      for(const key of columns){
        if(key==='id'||key==='type'||(tab==='levels'&&key==='level'))cell(tr,key==='id'?label(row[key]):String(row[key]));
        else if(key==='aggressive'||key==='deathChase'){const input=node('input');input.type='checkbox';input.checked=row[key];input.dataset.row=row.id;input.dataset.field=key;input.onchange=()=>speciesEdit(row,key,input.checked,body);input.setAttribute('aria-label',`${row.nameEn||row.id} ${names[key]}`);cell(tr,input)}
        else if(key==='nameEn'||key==='nameRu'){const input=node('input');input.type='text';input.maxLength=100;input.value=row[key];input.dataset.row=row.id;input.dataset.field=key;input.placeholder='—';input.style.minWidth='180px';input.onchange=()=>{const value=input.value.trim();speciesEdit(row,key,value,body)};cell(tr,input)}
        else if(key==='price'&&row.recipe){const source=d.weapons.find(w=>w.id===row.recipe.swordId);const cost=node('span',String(2*source.price+row.recipe.fee));cost.dataset.recipeCost=row.id;cell(tr,cost)}
        else if(key==='rarity')cell(tr,select(['common','uncommon','rare','mythical','legendary','immortal'].map(v=>[v,v]),row[key],v=>{row[key]=v;change()}));
        else if(key==='aggroRadiusStuds'){const input=number(row[key],v=>speciesEdit(row,key,v,body));input.dataset.row=row.id;input.dataset.field=key;cell(tr,input)}
        else cell(tr,number(row[key],v=>{row[key]=v;updateDerived();if(tab==='levels'&&key==='xpNext'){let sum=0;for(const [i,r] of d.levels.entries()){body.rows[i].lastElementChild.textContent=String(sum);sum+=r.xpNext||0}}}));
      }
      if(tab==='levels'){cell(tr,String(total));total+=row.xpNext||0}
      if(tab==='weapons'){gradeCell=node('span');cell(tr,gradeCell);derived=node('span');cell(tr,derived);updateDerived();const recipe=node('span');if(row.recipe){recipe.textContent=`2 × ${label(row.recipe.swordId)} + `;recipe.append(number(row.recipe.fee,v=>{row.recipe.fee=v}));}cell(tr,recipe)}
      body.append(tr);
    }
  }
  async function load(force=false){if(busy)return;if(hasChanges()&&!force){render();return}if(hasChanges()&&!confirm('Discard unsaved Database changes?'))return;busy=true;status('Loading…');try{snapshot=await request('/api/balance');dirty=false;spawnChanges.clear();spawnData=null;status('Ready')}catch(e){status(e.message)}finally{busy=false;render()}}
  async function save(){
    if(busy||!snapshot||!hasChanges())return;
    busy=true;$('balance-save').disabled=true;const content=$('balance-content');content.inert=true;$('balance-tabs').inert=true;
    let balanceSaved=false;
    try{
      if(dirty){snapshot=await request('/api/balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({balance:snapshot.balance,revision:snapshot.revision})});dirty=false;balanceSaved=true}
      if(spawnChanges.size){
        const result=await request('/api/monster-spawns/database-update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({updates:[...spawnChanges.values()]})});
        if(spawnData)for(const r of result.records){const i=spawnData.records.findIndex(v=>v.spawnId===r.spawnId);if(i>=0)spawnData.records[i]=r}
        spawnChanges.clear();
      }
      status('Saved · Rojo Sync required');
    }catch(e){status((balanceSaved?'Balance saved; spawn changes unsaved · ':'')+e.message)}
    finally{busy=false;content.inert=false;$('balance-tabs').inert=false;render()}
  }

  $('balance-reload').onclick=()=>load(true);$('balance-save').onclick=save;
  let logsLoading=false;
  async function loadLogs(){
    if(logsLoading)return;logsLoading=true;
    const status=$('balance-logs-status'),rows=$('balance-logs-rows'),refresh=$('balance-logs-refresh');
    refresh.disabled=true;status.textContent='Loading…';
    try{
      const data=await request('/api/balance/logs');
      rows.replaceChildren(...data.entries.map(entry=>{
        const li=node('li',entry.message+' · M'+entry.patch);return li;
      }));status.textContent=data.entries.length?'':'No changes yet';
    }catch(e){rows.replaceChildren();status.textContent=e.message}
    finally{logsLoading=false;refresh.disabled=false}
  }
  $('balance-logs-refresh').onclick=loadLogs;
  window.game1BalanceOpen=(target='main')=>{
    for(const [key,panel,nav] of [['main','balance-panel','nav-balance'],['history','database-history-panel','nav-asset-audit'],['logs','balance-logs-panel','nav-balance-logs']]){
      $(panel).hidden=target!==key;$(nav).classList.toggle('active',target===key);
    }
    if(target==='history')window.game1AssetAuditLoad?.();
    else if(target==='logs')loadLogs();
    else {load();window.game1WeaponMovementLoad?.()}
  };
})();
