/* Shared canonical balance revision. Skills and test assignments are separate views,
   not a duplicate database. No client-derived downgrade is saved. */
(() => {
  const buffs=new Set(['might','haste']);
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
  let snapshot=null,dirty=false,busy=false,owner='monster',kind='debuff';
  const status=t=>{for(const id of ['skills-status','skilled-status'])$(id).textContent=t};
  const buttons=()=>{for(const id of ['skills-save','skilled-save'])$(id).disabled=busy||!dirty||!snapshot};
  function change(){dirty=true;buttons();status('Unsaved · downgrade recalculated on save');}
  function action(text,fn){const b=el('button',text);b.type='button';b.onclick=fn;return b}
  function select(options,value,fn){const n=el('select');for(const [v,t] of options){const o=el('option',t);o.value=v;n.append(o)}n.value=value;n.onchange=()=>{fn(n.value);change()};return n}
  function num(value,fn,min,max,step='any'){const n=el('input');n.type='number';n.min=min;n.max=max;n.step=step;n.value=value;n.style.width='82px';n.oninput=()=>{fn(n.value===''?null:Number(n.value));change()};return n}
  function check(text,value,fn){const l=el('label'),n=el('input');n.type='checkbox';n.checked=value;n.onchange=()=>{fn(n.checked);change()};l.append(n,document.createTextNode(' '+text));return l}
  function cell(tr,value){const n=el('td');if(typeof value==='string')n.textContent=value;else n.append(value);tr.append(n)}
  function table(parent,cols){const t=el('table'),h=el('thead'),r=el('tr'),b=el('tbody');for(const c of cols)r.append(el('th',c));h.append(r);t.append(h,b);parent.append(t);return b}
  function renderSkills(){
    const root=$('skills-editor');root.replaceChildren();if(!snapshot)return;
    const tabs=el('div');tabs.className='actions';
    for(const [v,t] of [['monster','Monsters'],['character','Characters']]){const b=action(t,()=>{owner=v;renderSkills()});b.className=v===owner?'primary':'';tabs.append(b)}
    for(const [v,t] of [['debuff','Debuff'],['buff','Buff']]){const b=action(t,()=>{kind=v;renderSkills()});b.className=v===kind?'primary':'';tabs.append(b)}root.append(tabs);
    if(owner==='character'){root.append(el('p','Character skills are not enabled yet.'));return}
    const samples=snapshot.balance.skills.filter(s=>buffs.has(s.effect)===(kind==='buff'));
    const source=el('select');for(const sample of samples){const option=el('option',sample.name);option.value=sample.id;source.append(option)}
    const add=action('+ Skill variant',()=>{if(snapshot.balance.skills.length>=64)return;const sample=samples.find(s=>s.id===source.value);if(!sample)return;snapshot.balance.skills.push({...sample,id:'skill_'+crypto.randomUUID().replaceAll('-',''),name:(sample.name+' variant').slice(0,60)});change();renderSkills()});root.append(source,add);
    const body=table(root,['Skill ID','Effect','Name','Power %','Duration · s','Cooldown · s','Tick · s']);
    for(const s of snapshot.balance.skills.filter(s=>buffs.has(s.effect)===(kind==='buff'))){const tr=el('tr');cell(tr,s.id);cell(tr,s.effect);
      const name=el('input');name.value=s.name;name.maxLength=60;name.oninput=()=>{s.name=name.value;change()};cell(tr,name);
      const p=num(s.power,v=>s.power=v,1,100);p.disabled=['root','stun','silence'].includes(s.effect);cell(tr,p);cell(tr,num(s.duration,v=>s.duration=v,.5,20));cell(tr,num(s.cooldown,v=>s.cooldown=v,1.5,120));
      cell(tr,['poison','bleed'].includes(s.effect)?num(s.tick,v=>s.tick=v,.5,20):'—');body.append(tr);
    }
    root.append(el('p','Power: DoT = % of downgraded base hit per tick; Slow = movement reduction; Might / Haste = stat bonus. Silence is reserved for future character skills.'));
  }
  function renderProfiles(){
    const root=$('skilled-editor');root.replaceChildren();if(!snapshot)return;
    const data=snapshot.balance,top=el('div');top.className='actions';top.append(check('Spawn skilled monsters',data.test.skilledEnabled,v=>data.test.skilledEnabled=v));
    const add=action('+ Monster',()=>{if(data.skilledMonsters.length>=24)return;const s=data.skills.find(s=>!buffs.has(s.effect))||data.skills[0];if(!s)return;data.skilledMonsters.push({id:'skilled_'+crypto.randomUUID().replaceAll('-',''),level:20,type:'melee',skills:[{skillId:s.id,downgrade:true,trigger:buffs.has(s.effect)?'hpBelow':'cast',hpBelow:50}]});change();renderProfiles()});top.append(add);root.append(top);
    const saved=new Map((snapshot.resolvedSkilledMonsters||[]).map(r=>[r.id,r]));
    for(const p of data.skilledMonsters){const panel=el('div');panel.className='panel character-card';const header=el('div');header.className='actions';
      const names=()=>p.skills.map(a=>data.skills.find(s=>s.id===a.skillId)?.name||a.skillId).join(' + ');
      header.append(el('strong',names()),el('span','LVL'),num(p.level,v=>p.level=v,1,35,1),select([['melee','Melee'],['ranged','Ranged']],p.type,v=>p.type=v),action('Remove',()=>{data.skilledMonsters=data.skilledMonsters.filter(r=>r!==p);change();renderProfiles()}));
      panel.append(header);const r=saved.get(p.id);if(r)panel.append(el('small',`Saved: ${r.hp} HP · ${r.damage} ATK · downgrade ${((1-r.factor)*100).toFixed(1)}%`));
      const body=table(panel,['Skill','Downgrade','Trigger','HP below %','']);
      for(const a of p.skills){const s=data.skills.find(s=>s.id===a.skillId);const isBuff=buffs.has(s?.effect);const tr=el('tr');
        const choices=data.skills.filter(x=>buffs.has(x.effect)===isBuff && !p.skills.some(other=>other!==a&&data.skills.find(y=>y.id===other.skillId)?.effect===x.effect));
        cell(tr,select(choices.map(x=>[x.id,x.name]),a.skillId,v=>{a.skillId=v;queueMicrotask(renderProfiles)}));const budget=r?.skillBudgets?.[a.skillId];cell(tr,check(budget==null?'Auto':`Auto −${(100*budget/(1+budget)).toFixed(1)}%`,a.downgrade,v=>a.downgrade=v));
        cell(tr,isBuff?select([['attacked','Was attacked'],['hpBelow','HP below'],['expired','Effect expired']],a.trigger,v=>{a.trigger=v;queueMicrotask(renderProfiles)}):'Independent cast');
        cell(tr,isBuff&&a.trigger==='hpBelow'?num(a.hpBelow,v=>a.hpBelow=v,1,99,1):'—');cell(tr,action('−',()=>{if(p.skills.length===1)return;p.skills=p.skills.filter(x=>x!==a);change();renderProfiles()}));body.append(tr);
      }
      const actions=el('div');actions.className='actions';for(const isBuff of [false,true]){const b=action(isBuff?'+ Buff':'+ Debuff',()=>{const s=data.skills.find(x=>buffs.has(x.effect)===isBuff&&!p.skills.some(a=>data.skills.find(y=>y.id===a.skillId)?.effect===x.effect));if(!s||p.skills.length>=8)return;p.skills.push({skillId:s.id,downgrade:true,trigger:isBuff?'hpBelow':'cast',hpBelow:50});change();renderProfiles()});b.disabled=p.skills.length>=8||!data.skills.some(x=>buffs.has(x.effect)===isBuff&&!p.skills.some(a=>data.skills.find(y=>y.id===a.skillId)?.effect===x.effect));actions.append(b)}panel.append(actions);root.append(panel);
    }
  }
  function render(){renderSkills();renderProfiles();buttons()}
  async function load(force=false){if(busy)return;if(dirty&&!force){render();return}if(dirty&&!confirm('Discard unsaved skill / profile changes?'))return;busy=true;buttons();status('Loading…');try{snapshot=await request('/api/balance');dirty=false;status('Ready')}catch(e){status(e.message)}finally{busy=false;render()}}
  async function save(){if(busy||!snapshot||!dirty)return;busy=true;buttons();$('skills-editor').inert=true;$('skilled-editor').inert=true;try{snapshot=await request('/api/balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({balance:snapshot.balance,revision:snapshot.revision})});dirty=false;status('Saved · Rojo Sync + restart Play')}catch(e){status(e.message)}finally{busy=false;$('skills-editor').inert=false;$('skilled-editor').inert=false;render()}}
  $('nav-skills').onclick=()=>window.game1BalanceOpen('skills');$('skills-reload').onclick=()=>load(true);$('skilled-reload').onclick=()=>load(true);$('skills-save').onclick=save;$('skilled-save').onclick=save;
  $('skilled-monsters-disclosure').addEventListener('toggle',()=>{if($('skilled-monsters-disclosure').open)load()});
  window.game1SkillsOpen=()=>load();
})();
