/* Database authoring: stable item IDs, explicit model bindings, revision guarded save. */
(() => {
  let snapshot=null, tab='levels', busy=false, dirty=false, section='balance';
  const gradeNames=['Newbie','D','C','B','A','S','SS','SSS'];
  window.game1EquipmentGrade=level=>{const band=Math.max(0,Math.min(7,Math.floor(level/10)));return {name:gradeNames[band]+(level%10>=5?'+':''),required:Math.max(1,band*10)}};
  const groups={rules:'Character',levels:'Levels',weapons:'Weapons',armor:'Armor',monsters:'Monsters',bindings:'Model bindings'};
  const fields={levels:['level','hp','xpNext'],weapons:['id','type','level','damage','price','attackSpeedDelta','critChance','radius','arc','rarity','upgradePrice'],armor:['id','level','hp','price'],monsters:['id','type','level','hp','damage','critChance','xp','gold','attackRange','attackSpeed','runSpeed']};
  const names={runSpeed:'RunSpeed · /10 studs/s',attackSpeed:'ASPD',attackRange:'Range · studs',level:'LVL',hp:'HP',xpNext:'XP → next',damage:'ATK bonus',price:'Price',attackSpeedDelta:'ASPD Δ',critChance:'Crit %',radius:'Radius',arc:'Arc °',rarity:'Rarity',upgradePrice:'Upgrade cost',xp:'XP',gold:'Gold',id:'ID',type:'Type'};
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
      for(const r of rows)if(kind==='Monster model'||r.type===model.type)options.push([r.id,`${label(r.id)} · ${r.type} · LVL ${r.level}`]);
      if(bindings[model.slug]&&!options.some(v=>v[0]===bindings[model.slug]))options.push([bindings[model.slug],`${label(bindings[model.slug])} · incompatible / retired`]);
      cell(tr,select(options,bindings[model.slug]||'',value=>{if(value)bindings[model.slug]=value;else delete bindings[model.slug];change()}));body.append(tr);
    }
  }
  function render(){
    $('balance-tabs').replaceChildren();$('balance-content').replaceChildren();$('balance-save').disabled=busy||!snapshot||!dirty;
    for(const [key,title] of Object.entries(groups)){const b=node('button',title);b.type='button';b.className=key===tab?'primary':'';b.onclick=()=>{tab=key;render()};$('balance-tabs').append(b)}
    if(!snapshot)return;
    const d=snapshot.balance;
    if(tab==='rules'){
      const body=table(['Parameter','Value']);for(const [key,val] of Object.entries(d.rules)){const tr=node('tr');cell(tr,({baseRunSpeed:'RunSpeed · /10 studs/s',monsterCastSeconds:'Special cast · s',critChance:'Unarmed crit %',maxCritChance:'Max crit %',critMultiplier:'Crit damage ×'}[key]||key));cell(tr,number(val,v=>d.rules[key]=v));body.append(tr)}return;
    }
    if(tab==='bindings'){
      bindingTable('Weapon model',snapshot.weaponModels,d.weaponBindings,d.weapons);
      bindingTable('Monster model',snapshot.monsterModels,d.monsterBindings,d.monsters);return;
    }
    const columns=fields[tab], headers=columns.map(k=>tab==='monsters'&&k==='damage'?'Damage':names[k]);if(tab==='levels')headers.push('Total XP');if(tab==='weapons')headers.push('Grade · required LVL','ATK +0 / max','Craft recipe · fee');
    const body=table(headers);let total=0;
    const rows=tab==='weapons'?[...d[tab]].sort((a,b)=>a.level-b.level||a.id.localeCompare(b.id)):d[tab];
    for(const row of rows){const tr=node('tr');let derived,gradeCell;
      function updateDerived(){if(gradeCell){const g=window.game1EquipmentGrade(row.level);gradeCell.textContent=`${g.name} · ${g.required}`}if(tab==='weapons'&&derived)derived.textContent=`${d.rules.baseDamage+row.damage} / ${d.rules.baseDamage+Math.round(row.damage*(1+d.rules.maxUpgrade*d.rules.upgradePercent/100))}`}
      for(const key of columns){
        if(key==='id'||key==='type'||(tab==='levels'&&key==='level'))cell(tr,key==='id'?label(row[key]):String(row[key]));
        else if(key==='price'&&row.recipe){const source=d.weapons.find(w=>w.id===row.recipe.swordId);const cost=node('span',String(2*source.price+row.recipe.fee));cost.dataset.recipeCost=row.id;cell(tr,cost)}
        else if(key==='rarity')cell(tr,select(['common','uncommon','rare','mythical','legendary','immortal'].map(v=>[v,v]),row[key],v=>{row[key]=v;change()}));
        else cell(tr,number(row[key],v=>{row[key]=v;updateDerived();if(tab==='levels'&&key==='xpNext'){let sum=0;for(const [i,r] of d.levels.entries()){body.rows[i].lastElementChild.textContent=String(sum);sum+=r.xpNext||0}}}));
      }
      if(tab==='levels'){cell(tr,String(total));total+=row.xpNext||0}
      if(tab==='weapons'){gradeCell=node('span');cell(tr,gradeCell);derived=node('span');cell(tr,derived);updateDerived();const recipe=node('span');if(row.recipe){recipe.textContent=`2 × ${label(row.recipe.swordId)} + `;recipe.append(number(row.recipe.fee,v=>{row.recipe.fee=v}));}cell(tr,recipe)}
      body.append(tr);
    }
  }
  async function load(force=false){if(busy)return;if(dirty&&!force){render();return}if(dirty&&!confirm('Discard unsaved balance changes?'))return;busy=true;status('Loading…');try{snapshot=await request('/api/balance');dirty=false;status('Ready')}catch(e){status(e.message)}finally{busy=false;render()}}
  async function save(){if(busy||!snapshot||!dirty)return;busy=true;$('balance-save').disabled=true;const content=$('balance-content');content.inert=true;$('balance-tabs').inert=true;try{snapshot=await request('/api/balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({balance:snapshot.balance,revision:snapshot.revision})});dirty=false;status('Saved · Rojo Sync required')}catch(e){status(e.message)}finally{busy=false;content.inert=false;$('balance-tabs').inert=false;render()}}
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
  window.game1BalanceOpen=(target=section)=>{
    section=target;
    for(const [key,panel,nav] of [['balance','balance-panel','nav-balance'],['skills','skills-panel','nav-skills'],['history','database-history-panel','nav-asset-audit'],['logs','balance-logs-panel','nav-balance-logs']]){
      $(panel).hidden=target!==key;$(nav).classList.toggle('active',target===key);
    }
    if(target==='skills')window.game1SkillsOpen?.();
    else if(target==='history')window.game1AssetAuditLoad?.();
    else if(target==='logs')loadLogs();
    else {load();window.game1WeaponMovementLoad?.()}
  };
})();
