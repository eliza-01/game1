/* Armor v2 authoring: set → optional slot → gender → reusable mesh + atlas.
   No FBX upload, no Roblox publication and no client-side persistence. */
(() => {
  const byId = id => document.getElementById('armor-' + id);
  const text = (tag, value) => { const node=document.createElement(tag);node.textContent=String(value??'');return node; };
  const post=(path,payload)=>request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const labels={upper:'Верх',lower:'Низ',gloves:'Перчатки',boots:'Ботинки'};
  const types={light:'Лёгкая',heavy:'Тяжёлая',magic:'Магическая'};
  const genders={unisex:'Unisex',male:'Male',female:'Female'};
  const ru='абвгдеёжзийклмнопрстуфхцчшщъыьэюя';
  const en=['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','sch','','y','','e','yu','ya'];
  const slug=value=>{
    let str=String(value||'').trim().toLowerCase();str=[...str].map(ch=>ru.includes(ch)?en[ru.indexOf(ch)]:ch).join('');
    return str.replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').replace(/_+/g,'_').slice(0,64);
  };
  let catalog=null,setId=null,pieceId=null,busy=false,editing=false,pendingResource=null;
  const selectedSet=()=>catalog?.sets.find(s=>s.id===setId);
  const selectedPiece=()=>selectedSet()?.pieces.find(p=>p.id===pieceId);
  function notice(message,error=false){byId('status').textContent=message;byId('status').classList.toggle('error',error);}
  function select(node,rows,value,placeholder){
    node.replaceChildren(new Option(placeholder,''));
    rows.forEach(item=>node.append(new Option(item.label,item.value)));
    node.value=value||'';
  }
  function summary(piece,gender){
    const variant=piece.variants[gender]||piece.variants.unisex;
    if(!variant)return '—';
    if(!variant.meshPartId&&!variant.appearanceId)return 'черновик';
    return (variant.meshPartId||'нет меша')+' / '+(variant.appearanceId||'нет текстуры');
  }
  function render(){
    if(!catalog)return;
    const list=byId('set-list');list.replaceChildren();
    for(const item of catalog.sets){
      const btn=text('button',`${item.display_name} · ${types[item.armor_type]} · ${item.pieces.length} слотов`);
      btn.type='button';btn.className='armor-set'+(item.id===setId?' armor-selected':'');
      btn.onclick=()=>{setId=item.id;pieceId=item.pieces[0]?.id||null;editing=false;render();};
      list.append(btn);
    }
    if(!catalog.sets.length)list.append(text('p','Комплектов пока нет. Начни с названия и типа.'));
    const set=selectedSet();
    const creating=byId('set-form');
    byId('create').textContent=editing&&set?'Сохранить комплект':'Зарегистрировать комплект';
    byId('set-new').hidden=!editing;
    byId('set-edit').hidden=!set||editing;
    if(!editing){creating.elements.namedItem('displayName').value='';creating.elements.namedItem('armorType').value='light';}
    byId('set-title').textContent=set?`${set.display_name} · ${set.id}`:'Сначала зарегистрируй комплект';
    const slots=byId('slots');slots.replaceChildren();
    if(set){
      const available=catalog.slots.filter(slot=>!set.pieces.some(p=>p.slot===slot));
      select(byId('add-slot'),available.map(v=>({label:labels[v],value:v})),'','Выбери часть комплекта…');
      byId('add').disabled=busy||!available.length||!byId('add-slot').value;
      for(const piece of set.pieces){
        const row=document.createElement('div');row.className='armor-piece-row';
        const button=text('button',`${labels[piece.slot]} · M: ${summary(piece,'male')} · F: ${summary(piece,'female')}`);
        button.type='button';button.className=piece.id===pieceId?'armor-selected':'';
        button.onclick=()=>{pieceId=piece.id;render();};
        const remove=text('button','×');remove.type='button';remove.title='Удалить эту часть из комплекта';
        remove.onclick=()=>perform(async()=>{
          if(!confirm('Удалить '+labels[piece.slot]+' из '+set.display_name+'? Меши и атласы останутся в библиотеке.'))return;
          catalog=await post('/api/armor/pieces/remove',{pieceId:piece.id});
          if(pieceId===piece.id)pieceId=null;
          render();window.dispatchEvent(new Event('character-armor-changed'));
        });
        row.append(button,remove);slots.append(row);
      }
    }
    byId('add-controls').hidden=!set;
    byId('variant-controls').hidden=!selectedPiece();
    byId('stats').hidden=!set;
    if(set){
      const ready=gender=>set.pieces.filter(p=>{
        const v=p.variants[gender]||p.variants.unisex;
        return !!v?.meshPartId&&!!v?.appearanceId;
      }).length;
      byId('readiness').textContent=`Назначено частей: male ${ready('male')}/${set.pieces.length} · female ${ready('female')}/${set.pieces.length}. Отсутствующие слоты допустимы.`;
    }else byId('readiness').textContent='';
    if(selectedPiece())renderVariant();
  }
  function renderVariant(){
    const piece=selectedPiece();if(!piece)return;
    const gender=byId('gender').value||'unisex',saved=piece.variants[gender]||{};
    const gendersNeeded=gender==='unisex'?['male','female']:[gender];
    const meshes=catalog.meshes.filter(m=>m.slot===piece.slot&&gendersNeeded.every(g=>m.allowedGenders.includes(g)));
    select(byId('mesh'),meshes.map(m=>({label:`${m.id} · ${m.mesh_family_id} · ${m.model_asset_id?'Model '+m.model_asset_id:'не опубликован'}`,value:m.id})),saved.meshPartId,'Без меша · назначить позже');
    const atlasId=catalog.appearances.find(a=>a.id===saved.appearanceId)?.atlas_variant_id;
    select(byId('atlas'),catalog.atlases.map(a=>({label:`${a.atlas_key} · ${a.resolution} · ${a.current?'опубликован':'черновик'}`,value:String(a.id)})),atlasId&&String(atlasId),'Без текстуры · назначить позже');
    if(pendingResource){
      const control=byId(pendingResource.kind==='mesh'?'mesh':'atlas');
      if([...control.options].some(option=>option.value===pendingResource.value)){
        control.value=pendingResource.value;
        notice('Ресурс выбран. Нажми «Сохранить вариант», чтобы закрепить его за этим слотом.');
        pendingResource=null;
      }
    }
    byId('variant-title').textContent=`${labels[piece.slot]} · ${genders[gender]}`;
    byId('variant-note').textContent=gender==='unisex'?'Этот вариант подходит обоим полам. Male/Female варианты имеют приоритет.':
      'Настройка влияет только на этот пол. Не изменяет геометрию или текстуру в других комплектах.';
  }
  async function perform(action){
    if(busy)return;busy=true;
    for(const b of [byId('create'),byId('add'),byId('save')])b.disabled=true;
    try{await action();}catch(error){notice(error.message,true);}finally{busy=false;for(const b of [byId('create'),byId('save')])b.disabled=false;byId('add').disabled=!byId('add-slot').value;}
  }
  async function refresh(){
    catalog=await request('/api/armor');
    if(setId&&!selectedSet()){setId=null;pieceId=null;editing=false;}
    if(pieceId&&!selectedPiece())pieceId=selectedSet()?.pieces[0]?.id||null;
    render();
  }
  byId('set-form').onsubmit=event=>{
    event.preventDefault();
    perform(async()=>{
      const name=byId('name').value.trim();
      const id=editing&&selectedSet()?setId:slug(name);
      if(!id)throw Error('Введите название комплекта буквами или цифрами');
      catalog=await post('/api/armor/sets',{id,displayName:name,armorType:byId('type').value,
        expectedRevision:editing&&selectedSet()?selectedSet().revision:0});
      setId=id;pieceId=selectedSet()?.pieces[0]?.id||null;editing=false;
      render();notice('Комплект сохранён. Добавь только нужные части.');
      window.dispatchEvent(new Event('character-armor-changed'));
    });
  };
  byId('set-edit').onclick=()=>{
    const s=selectedSet();if(!s)return;
    editing=true;render();byId('name').value=s.display_name;byId('type').value=s.armor_type;
    byId('name').focus();
  };
  byId('set-new').onclick=()=>{editing=false;render();};
  byId('add-slot').onchange=()=>{byId('add').disabled=!byId('add-slot').value;};
  byId('add').onclick=()=>perform(async()=>{
    const slot=byId('add-slot').value;if(!slot)return;
    catalog=await post('/api/armor/pieces',{setId,slot});
    pieceId=setId+'_'+slot;render();notice('Часть создана без геометрии и атласа. Можно назначить их позже.');
    window.dispatchEvent(new Event('character-armor-changed'));
  });
  byId('gender').onchange=renderVariant;
  byId('save').onclick=()=>perform(async()=>{
    const piece=selectedPiece();if(!piece)throw Error('Выбери часть комплекта');
    const gender=byId('gender').value,old=piece.variants[gender];
    catalog=await post('/api/armor/variants',{pieceId:piece.id,gender,
      meshPartId:byId('mesh').value||null,atlasVariantId:byId('atlas').value?Number(byId('atlas').value):null,
      expectedRevision:old?.revision||0});
    render();notice('Вариант сохранён. Опубликованные MeshPart и атлас повторно используются.');
    window.dispatchEvent(new Event('character-armor-changed'));
  });
  window.game1ArmorCatalog={
    assignResource:(kind,value)=>{
      pendingResource={kind,value:String(value)};
      byId('panel').scrollIntoView({behavior:'smooth'});
      if(!catalog?.sets.length){
        notice('Сначала зарегистрируй комплект, добавь слот и выбери Male/Female/Unisex.');return;
      }
      if(kind==='mesh'){
        const mesh=catalog.meshes.find(row=>row.id===value);
        const target=selectedSet()?.pieces.find(piece=>piece.slot===mesh?.slot);
        if(target)pieceId=target.id;
      }
      render();
      if(pendingResource)notice('Ресурс запомнен. Выбери подходящий комплект, слот и пол — затем сохрани вариант.');

    }
  };
  window.addEventListener('character-components-changed',()=>refresh().catch(err=>notice(err.message,true)));
  refresh().catch(err=>notice(err.message,true));
})();
