/* Startup/debug assembly v2. Equipment comes only from Armor Catalog. */
(() => {
  const base='/api/characters/assemblies';
  const byId=id=>document.getElementById('ca-'+id);
  const slots=['head','eye_l','eye_r','eyebrow_l','eyebrow_r','hair'];
  const solidFaceSlots=['eye_l','eye_r','eyebrow_l','eyebrow_r'];
  const atlasSlots=['head','hair'];
  const labels={head:'Голова',eye_l:'Левый глаз',eye_r:'Правый глаз',eyebrow_l:'Левая бровь',eyebrow_r:'Правая бровь',hair:'Волосы'};
  const post=(url,payload)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=String(value??'');return n;};
  let data=null,selected=null,revision=0,original='',busy=false;
  const current=id=>data?.items.find(row=>row.id===id);
  function message(value,error=false){byId('status').textContent=value;byId('status').classList.toggle('error',error);}
  function setSelect(control,items,value,placeholder='Choose…'){
    control.replaceChildren(new Option(placeholder,''));
    for(const item of items)control.append(new Option(item.label,item.value));
    control.value=value||'';
  }
  function faceRows(slot){
    return (data?.catalog.items||[]).filter(row=>row.kind==='part'&&row.slot===slot&&row.role==='part'
      &&(row.compatibleRigIds||[]).includes(byId('rig').value)&&(row.allowedGenders||[]).includes(byId('gender').value));
  }
  function hairColors(){
    if(!byId('slot-hair')?.value)return {};
    return Object.fromEntries([...byId('hair-colors').querySelectorAll('input[data-hair-channel]')]
      .map(input=>[input.dataset.hairChannel,input.value.toUpperCase()]));
  }
  function fillHairColors(saved={}){
    const host=byId('hair-colors');host.replaceChildren();
    const id=byId('slot-hair').value;
    const hair=(data?.catalog.items||[]).find(row=>row.id===id&&row.slot==='hair');
    if(!hair||hair.metadata?.attachment_mode!=='pivot')return;
    const channels=[['primary','Волосы'],...(hair.metadata?.extras||[])
      .map(item=>[item.name.slice(id.length+1),`Доп. элемент ${item.name.slice(-2)}`])];
    for(const [channel,name] of channels){
      const label=text('label',`Цвет · ${name}`);
      const color=document.createElement('input');color.type='color';color.dataset.hairChannel=channel;
      color.value=saved[channel]||'#ffffff';color.oninput=update;
      label.append(color);host.append(label);
    }
  }
  function payload(){
    return {id:byId('id').value.trim(),display_name:byId('name').value.trim(),rig_id:byId('rig').value,
      gender:byId('gender').value,armor_set_id:byId('set').value,
      face_parts:Object.fromEntries(slots.map(slot=>[slot,byId('slot-'+slot).value])),
      face_atlases:Object.fromEntries(atlasSlots.map(slot=>[slot,byId('atlas-'+slot).value])),
      face_colors:Object.fromEntries(solidFaceSlots.filter(slot=>byId('slot-'+slot).value)
        .map(slot=>[slot,byId('color-'+slot).value.toUpperCase()])),
      hair_colors:hairColors(),
      stats:Object.fromEntries((data?.stats.statKeys||[]).map(key=>[key,Number(byId('stat-'+key).value)]))};
  }
  function formDirty(){return !!data&&!!original&&JSON.stringify(payload())!==original;}
  function canDiscard(){return !formDirty()||confirm('Отменить несохранённые изменения?');}
  function fillFaces(values={},textures={},colors={}){
    for(const slot of slots){
      setSelect(byId('slot-'+slot),faceRows(slot).map(row=>({label:row.id+(row.model_asset_id?'':' · unpublished'),value:row.id})),values[slot]);
      if(atlasSlots.includes(slot)){
        setSelect(byId('atlas-'+slot),data.armor.atlases.map(v=>({label:v.atlas_key+' · '+v.resolution+(v.current?'':' · unpublished'),value:String(v.id)})),
          textures[slot], 'Без атласа / solid');
      }else{
        byId('color-'+slot).value=colors[slot]||'#ffffff';
      }
    }
  }
  function fillSets(wanted=''){
    setSelect(byId('set'),data.armor.sets.map(s=>({label:s.display_name+' · '+s.id+' · '+s.pieces.length+' slots',value:s.id})),wanted,'Выбери зарегистрированный комплект…');
  }
  function update(){
    if(!data)return;
    const p=payload(),changes=formDirty();
    byId('save').disabled=busy||!p.id||!p.rig_id||!p.armor_set_id||!p.face_parts.head||!changes;
    byId('save').classList.toggle('character-dirty',!!changes);
    byId('editor-summary').textContent=selected?
      `${selected} · revision ${revision}${changes?' · не сохранено':''}`:'Новая отладочная сборка · v2';
    const chosen=data.armor.sets.find(s=>s.id===p.armor_set_id);
    byId('mix').textContent=chosen?`Сет: ${chosen.display_name} · части: ${chosen.pieces.map(x=>labels[x.slot]||x.slot).join(', ')||'пустой'}`:
      'Нужен комплект из Armor Catalog. Пустые слоты допустимы.';
    const errors=[];
    if(!p.rig_id)errors.push('Выбери скелет');
    if(!chosen)errors.push('Выбери комплект брони');
    if(!p.face_parts.head)errors.push('Выбери голову');
    for(const slot of slots){
      if(p.face_parts[slot]&&!faceRows(slot).some(row=>row.id===p.face_parts[slot]))errors.push(labels[slot]+': не совместимо с полом/ригом');
    }
    if(chosen){
      for(const piece of chosen.pieces){
        const v=piece.variants[p.gender]||piece.variants.unisex;
        if(!v?.meshPartId||!v?.appearanceId)errors.push(labels[piece.slot]+': отсутствует '+p.gender+' mesh/texture');
      }
    }
    byId('readiness').replaceChildren(text('strong',errors.length?'Черновик · '+errors.length+' недостающих зависимостей':'Можно сохранить и проверить публикации'));
    if(errors.length){const ul=document.createElement('ul');errors.forEach(x=>ul.append(text('li',x)));byId('readiness').append(ul);}
  }
  function edit(row){
    selected=row.id;revision=row.revision;byId('id').readOnly=true;
    const r=row.assembly?.schema_version===2?row.assembly:{};
    byId('id').value=row.id;byId('name').value=row.display_name;
    byId('rig').value=r.rig_id||'';byId('gender').value=r.gender||row.gender||'male';
    fillSets(r.armor_set_id||'');
    const faces=Object.fromEntries(slots.map(slot=>[slot,r.face_parts?.[slot]?.meshPartId||'']));
    const textures=Object.fromEntries(slots.map(slot=>[slot,String(data.armor.appearances.find(a=>a.id===r.face_parts?.[slot]?.appearanceId)?.atlas_variant_id||'')]));
    fillFaces(faces,textures,r.face_colors||{});fillHairColors(r.hair_colors||{});
    for(const key of data.stats.statKeys)byId('stat-'+key).value=row.stats[key];
    original=JSON.stringify(payload());update();
    message(r.schema_version===2?(row.assembly_resolved.ready?'READY':'DRAFT: '+row.assembly_resolved.missing.join(' · ')):
      'Старый v1 рецепт отключён. Выбери новый Armor set и сохрани как v2.',r.schema_version!==2);
  }
  function newDraft(){
    selected=null;revision=0;byId('id').readOnly=false;
    let id='human_female',i=2;while(data.items.some(x=>x.id===id))id='human_female_'+i++;
    byId('id').value=id;byId('name').value='Human Female';
    byId('gender').value='female';
    byId('rig').value=data.catalog.items.find(x=>x.kind==='rig'&&x.id==='human_female')?.id||'';
    fillSets('');fillFaces();fillHairColors();
    for(const key of data.stats.statKeys)byId('stat-'+key).value=data.stats.defaultStats[key];
    original=JSON.stringify(payload());update();
    message('Базовый Human Female: выбери опубликованный rig, Armor set и голову. Глаза, брови и волосы выбираются отдельно.');
  }
  function render(){
    byId('rows').replaceChildren();
    for(const row of data.items){
      const tr=document.createElement('tr');
      if(row.id===selected)tr.classList.add('character-selected-assembly');
      const r=row.assembly||{},ready=!!row.assembly_resolved?.ready;
      tr.append(text('td',row.display_name+' · '+row.id),text('td',r.rig_id||'—'),
        text('td',r.gender||row.gender),text('td',r.armor_set_id||'v1 retired'),
        text('td',ready?'READY':'DRAFT · '+(row.assembly_resolved?.missing||[]).join(' · ')));
      const buttons=document.createElement('td'),editButton=text('button','Edit');editButton.type='button';
      editButton.onclick=()=>{if(!busy&&canDiscard()){edit(row);render();byId('editor-summary').scrollIntoView({behavior:'smooth'});}};
      buttons.append(editButton);
      for(const purpose of ['default','admin']){
        const active=(purpose==='admin'?data.admin_id:data.default_id)===row.id;
        if(active){buttons.append(text('span',purpose==='admin'?'✓ Studio admin':'✓ Default'));continue;}
        const pick=text('button',purpose==='admin'?'Set as admin':'Set as default');
        pick.type='button';pick.disabled=busy||!ready;
        pick.onclick=()=>run(async()=>{
          if(!canDiscard())return;
          await post('/api/characters/assemblies/profile',{id:row.id,purpose});
          await refresh();await loadCharacters();
          message(purpose==='admin'?'Studio admin готов. Запусти новый Play.':'Базовая сборка сохранена для создания персонажа.');
        });
        buttons.append(pick);
      }
      tr.append(buttons);byId('rows').append(tr);
    }
  }
  async function refresh(){
    const pending=formDirty(),editId=selected,remember=pending?payload():null;
    data=await request(base);
    setSelect(byId('rig'),data.catalog.items.filter(x=>x.kind==='rig').map(x=>({label:x.id,value:x.id})),
      remember?.rig_id||byId('rig').value,'Rig…');
    if(remember){
      byId('gender').value=remember.gender;fillSets(remember.armor_set_id);fillFaces(remember.face_parts,remember.face_atlases,remember.face_colors);fillHairColors(remember.hair_colors);
      update();message('Catalog refreshed, unsaved edits retained.');
    }else if(editId&&current(editId))edit(current(editId));
    else if(!editId&&byId('id').value) newDraft();
    else {const active=data.items.find(x=>x.id===(data.default_id||data.admin_id))||data.items[0];if(active)edit(active);else newDraft();}
    render();
  }
  async function run(fn){if(busy)return;busy=true;byId('save').disabled=true;
    try{await fn();}catch(error){message(error.message,true);}finally{busy=false;update();}}
  const col=document.createElement('section');col.className='ca-part-column';
  col.append(text('h5','Лицо · геометрия и appearance'));
  for(const slot of slots){
    const label=text('label',labels[slot]);const part=document.createElement('select');part.id='ca-slot-'+slot;
    label.append(part);col.append(label);
    if(atlasSlots.includes(slot)){
      const atlasLabel=text('label','Атлас · '+labels[slot]);const atlas=document.createElement('select');atlas.id='ca-atlas-'+slot;
      atlasLabel.append(atlas);col.append(atlasLabel);atlas.onchange=update;
    }else{
      const colorLabel=text('label','Цвет · '+labels[slot]);const color=document.createElement('input');
      color.type='color';color.id='ca-color-'+slot;color.value='#ffffff';color.oninput=update;
      colorLabel.append(color);col.append(colorLabel);
    }
    part.onchange=()=>{if(slot==='hair')fillHairColors();update();};
  }
  const hairColorsRow=document.createElement('div');hairColorsRow.id='ca-hair-colors';
  col.append(hairColorsRow);
  byId('parts').append(col);
  for(const input of ['rig','gender'])byId(input).onchange=()=>{fillFaces();fillHairColors();update();};
  byId('set').onchange=update;
  for(const field of ['id','name'])byId(field).oninput=update;
  byId('new').onclick=()=>{if(data&&!busy&&canDiscard()){newDraft();render();}};
  byId('reset').onclick=()=>{if(data&&!busy){if(selected&&current(selected))edit(current(selected));else newDraft();render();}};
  byId('refresh').onclick=()=>run(refresh);
  byId('save').onclick=()=>run(async()=>{
    const body={...payload(),expected_revision:revision};
    data=await post(base,body);
    edit(current(body.id));render();await loadCharacters();
    message(current(body.id).assembly_resolved.ready?'Saved · ready for Studio Play.':'Saved draft · missing published dependencies.');
  });
  window.addEventListener('character-components-changed',()=>{if(data&&!busy)refresh().catch(e=>message(e.message,true));});
  window.addEventListener('character-armor-changed',()=>{if(data&&!busy)refresh().catch(e=>message(e.message,true));});
  window.game1CharacterAssemblies={edit:id=>{const row=current(id);if(row&&!busy&&canDiscard()){edit(row);render();document.getElementById('character-assemblies-panel').open=true;
      byId('editor-summary').scrollIntoView({behavior:'smooth'});}},
    create:()=>{if(data&&!busy&&canDiscard()){newDraft();render();}}};
  request(base).then(snapshot=>{
    data=snapshot;
    for(const key of data.stats.statKeys){
      const label=text('label',key),input=document.createElement('input');input.type='number';input.id='ca-stat-'+key;
      input.min=key==='Level'?'1':'0';input.step='any';label.append(input);byId('stats').append(label);input.oninput=update;
    }
    return refresh();
  }).catch(e=>message(e.message,true));
})();
