/* Database/Main/Skills view. Parent owns the sole balance draft and save. */
(() => {
  const buffs=new Set(['might','haste','earth','life','wind']);
  const shopIds=new Set(['skill_might_d','skill_earth_d','skill_life_d','skill_wind_d']);
  const unit=e=>({might:'% ATK',haste:'% ASPD',earth:'% HP',life:'HP/s',wind:'Speed',poison:'% hit/tick',bleed:'% hit/tick',slow:'% speed'}[e]||'Control');
  const skillLabel=s=>`${s.name}${shopIds.has(s.id)?' · D':''} · ${s.duration}s`;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
  let snapshot=null,root=null,kind='buff',change=()=>{},applySearch=()=>{};
  function action(text,fn){const b=el('button',text);b.type='button';b.onclick=fn;return b}
  function select(options,value,fn){const n=el('select');for(const [v,t] of options){const o=el('option',t);o.value=v;n.append(o)}n.value=value;n.onchange=()=>{fn(n.value);change()};return n}
  function num(value,fn,min,max,step='any'){const n=el('input');n.type='number';n.min=min;n.max=max;n.step=step;n.value=value;n.style.width='82px';n.oninput=()=>{fn(n.value===''?null:Number(n.value));change()};return n}
  function check(text,value,fn){const l=el('label'),n=el('input');n.type='checkbox';n.checked=value;n.onchange=()=>{fn(n.checked);change()};l.append(n,document.createTextNode(' '+text));return l}
  function cell(tr,value){const n=el('td');if(typeof value==='string')n.textContent=value;else n.append(value);tr.append(n)}
  function table(parent,cols){const t=el('table'),h=el('thead'),r=el('tr'),b=el('tbody');for(const c of cols)r.append(el('th',c));h.append(r);t.append(h,b);parent.append(t);return b}
  function renderSkills(){
    root.replaceChildren();if(!snapshot)return;
    const tabs=el('div');tabs.className='actions database-skill-tabs';
    for(const [v,t] of [['buff','Buff'],['debuff','Debuff'],['monster','Monster'],['character','Character']]){const b=action(t,()=>{kind=v;$('balance-search').value='';renderSkills();applySearch()});b.className=v===kind?'primary':'';tabs.append(b)}root.append(tabs);
    if(kind==='monster'){renderProfiles();return}
    if(kind==='character'){root.append(el('p','No character-specific skills registered. Shared Buff / Debuff effects are listed separately.'));return}
    const samples=snapshot.balance.skills.filter(s=>buffs.has(s.effect)===(kind==='buff')).sort((a,b)=>Number(shopIds.has(b.id))-Number(shopIds.has(a.id)));
    const top=el('div');top.className='actions database-skill-actions';
    const source=el('select');for(const sample of samples){const option=el('option',skillLabel(sample));option.value=sample.id;source.append(option)}
    const add=action('+ Variant',()=>{if(snapshot.balance.skills.length>=64)return;const sample=samples.find(s=>s.id===source.value);if(!sample)return;snapshot.balance.skills.push({...sample,id:'skill_'+crypto.randomUUID().replaceAll('-',''),name:(sample.name+' variant').slice(0,60)});change();renderSkills();applySearch()});top.append(source,add);root.append(top);
    const body=table(root,['Name','Effect','Power','Unit','Duration · s','Cooldown · s','Tick · s','ID']);
    for(const s of samples){const tr=el('tr');
      const name=el('input');name.value=s.name;name.maxLength=60;name.oninput=()=>{s.name=name.value;change()};cell(tr,name);
      cell(tr,s.effect+(shopIds.has(s.id)?' · D':''));
      const p=num(s.power,v=>s.power=v,1,100);p.disabled=['root','stun','silence'].includes(s.effect);cell(tr,p);cell(tr,unit(s.effect));
      const isBuff=buffs.has(s.effect);cell(tr,num(s.duration,v=>s.duration=v,.5,isBuff?3600:20));cell(tr,num(s.cooldown,v=>s.cooldown=v,1.5,isBuff?7200:120));
      cell(tr,['poison','bleed'].includes(s.effect)?num(s.tick,v=>s.tick=v,.5,20):'—');cell(tr,s.id);body.append(tr);
    }
    const hint=el('small',kind==='buff'?'D = Hub buffer variant. Cooldown applies to combat casts; shop blocks active duplicates.':'Shared effects · no actor ownership.');hint.className='muted';root.append(hint);
  }
  function renderProfiles(){
    const profileRoot=el('div');profileRoot.id='skilled-monsters-editor';root.append(profileRoot);if(!snapshot)return;
    profileRoot.append(el('h4','Skilled monsters · GP profiles'),el('small','Assignments of shared effects. Individual monster skills are not registered yet.'));
    const data=snapshot.balance,top=el('div');top.className='actions';top.append(check('Spawn skilled monsters',data.test.skilledEnabled,v=>data.test.skilledEnabled=v));
    const add=action('+ Monster',()=>{if(data.skilledMonsters.length>=24)return;const s=data.skills.find(s=>!buffs.has(s.effect))||data.skills[0];if(!s)return;data.skilledMonsters.push({id:'skilled_'+crypto.randomUUID().replaceAll('-',''),level:20,type:'melee',skills:[{skillId:s.id,downgrade:true,trigger:buffs.has(s.effect)?'hpBelow':'cast',hpBelow:50}]});change();renderSkills();applySearch()});top.append(add);profileRoot.append(top);
    const saved=new Map((snapshot.resolvedSkilledMonsters||[]).map(r=>[r.id,r]));
    for(const p of data.skilledMonsters){const panel=el('div');panel.className='panel character-card';const header=el('div');header.className='actions';
      const names=()=>p.skills.map(a=>data.skills.find(s=>s.id===a.skillId)?.name||a.skillId).join(' + ');
      header.append(el('strong',names()),el('span','LVL'),num(p.level,v=>p.level=v,1,35,1),select([['melee','Melee'],['ranged','Ranged']],p.type,v=>p.type=v),action('Remove',()=>{data.skilledMonsters=data.skilledMonsters.filter(r=>r!==p);change();renderSkills();applySearch()}));
      panel.append(header);const r=saved.get(p.id);if(r)panel.append(el('small',`Saved: ${r.hp} HP · ${r.damage} ATK · downgrade ${((1-r.factor)*100).toFixed(1)}%`));
      const body=table(panel,['Skill','Downgrade','Trigger','HP below %','']);
      for(const a of p.skills){const s=data.skills.find(s=>s.id===a.skillId);const isBuff=buffs.has(s?.effect);const tr=el('tr');
        const choices=data.skills.filter(x=>buffs.has(x.effect)===isBuff && !p.skills.some(other=>other!==a&&data.skills.find(y=>y.id===other.skillId)?.effect===x.effect));
        cell(tr,select(choices.map(x=>[x.id,skillLabel(x)]),a.skillId,v=>{a.skillId=v;queueMicrotask(()=>{renderSkills();applySearch()})}));const budget=r?.skillBudgets?.[a.skillId];cell(tr,check(budget==null?'Auto':`Auto −${(100*budget/(1+budget)).toFixed(1)}%`,a.downgrade,v=>a.downgrade=v));
        cell(tr,isBuff?select([['attacked','Was attacked'],['hpBelow','HP below'],['expired','Effect expired']],a.trigger,v=>{a.trigger=v;queueMicrotask(()=>{renderSkills();applySearch()})}):'Independent cast');
        cell(tr,isBuff&&a.trigger==='hpBelow'?num(a.hpBelow,v=>a.hpBelow=v,1,99,1):'—');cell(tr,action('−',()=>{if(p.skills.length===1)return;p.skills=p.skills.filter(x=>x!==a);change();renderSkills();applySearch()}));body.append(tr);
      }
      const actions=el('div');actions.className='actions';for(const isBuff of [false,true]){const b=action(isBuff?'+ Buff':'+ Debuff',()=>{const s=data.skills.find(x=>buffs.has(x.effect)===isBuff&&!p.skills.some(a=>data.skills.find(y=>y.id===a.skillId)?.effect===x.effect));if(!s||p.skills.length>=8)return;p.skills.push({skillId:s.id,downgrade:true,trigger:isBuff?'hpBelow':'cast',hpBelow:50});change();renderSkills();applySearch()});b.disabled=p.skills.length>=8||!data.skills.some(x=>buffs.has(x.effect)===isBuff&&!p.skills.some(a=>data.skills.find(y=>y.id===a.skillId)?.effect===x.effect));actions.append(b)}panel.append(actions);profileRoot.append(panel);
    }
  }
  window.game1RenderSkills=(parent,draft,markDirty,search)=>{root=parent;snapshot=draft;change=markDirty;applySearch=search;renderSkills()};
})();
