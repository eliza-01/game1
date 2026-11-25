/* Gameplay Test is a view of the same versioned balance, not a second database. */
(() => {
  let snapshot=null, busy=false;
  const config=$('gameplay-test-config'), status=$('gameplay-test-status'), save=$('gameplay-test-save');
  const fields={x:'Position X',y:'Position Y',z:'Position Z',yaw:'Orientation Y',maxGroup:'Max group (1–12)'};
  function render(){
    config.replaceChildren(); $('gameplay-test-tiers').replaceChildren();
    if(!snapshot){save.disabled=true;return}
    const d=snapshot.balance;
    for(const [key,name] of Object.entries(fields)){
      const label=document.createElement('label');label.textContent=name;
      const input=document.createElement('input');input.type='number';input.step=key==='maxGroup'?'1':'any';input.value=d.test[key];input.disabled=busy;
      input.oninput=()=>{d.test[key]=input.value===''?null:Number(input.value);save.disabled=busy;status.textContent='Unsaved test settings'};label.append(input);config.append(label);
    }
    const table=document.createElement('table'),head=document.createElement('thead'),body=document.createElement('tbody'),header=document.createElement('tr');
    for(const text of ['Grade','Item LVL','Required LVL','Weapon records','Armor HP','Monsters']){const th=document.createElement('th');th.textContent=text;header.append(th)}head.append(header);table.append(head,body);
    for(const level of [...new Set(d.weapons.map(w=>w.level))].sort((a,b)=>a-b)){
      const grade=window.game1EquipmentGrade(level),tr=document.createElement('tr');
      for(const text of [grade.name,level,grade.required,d.weapons.filter(w=>w.level===level).length,d.armor.find(a=>a.level===level)?.hp??'—',d.monsters.filter(m=>m.level>=level&&m.level<(level===1?5:level+5)).length]){const td=document.createElement('td');td.textContent=String(text);tr.append(td)}body.append(tr);
    }
    $('gameplay-test-tiers').append(table);
  }
  async function load(){if(busy)return;busy=true;save.disabled=true;status.textContent='Loading…';try{snapshot=await request('/api/balance');status.textContent='Ready · Studio only'}catch(e){status.textContent=e.message;snapshot=null}finally{busy=false;render()}}
  save.onclick=async()=>{if(!snapshot||busy)return;busy=true;save.disabled=true;render();try{snapshot=await request('/api/balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({balance:snapshot.balance,revision:snapshot.revision})});status.textContent='Saved · Rojo Sync required'}catch(e){status.textContent=e.message;save.disabled=false}finally{busy=false;render()}};
  $('gameplay-test-reload').onclick=load;window.game1GameplayTestLoad=load;
})();
