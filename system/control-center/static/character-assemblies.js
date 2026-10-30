/* Character recipes are UI-only compositions of registered parts; no FBX upload here. */
(() => {
  const base = '/api/characters/assemblies';
  const get = id => document.getElementById('ca-' + id);
  const slots = ['upper','lower','gloves','boots','head','eyes','eyebrows','hair'];
  const clothing = slots.slice(0,4);
  const icons = {upper:'👕',lower:'👖',gloves:'🧤',boots:'🥾',head:'🙂',eyes:'👁',eyebrows:'⌒',hair:'💇'};
  const labels = {upper:'Upper · chest',lower:'Lower · legs',gloves:'Gloves · hands',boots:'Boots · feet',
    head:'Head · determines gender',eyes:'Eyes',eyebrows:'Eyebrows',hair:'Hair · matching gender / common'};
  let data = null, selected = null, editRevision = 0, initialized = false, busy = false, original = null;
  const post = (url,payload) => request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const node = (tag,value) => {const n=document.createElement(tag);n.textContent=String(value??'');return n;};
  const current = id => data?.items.find(row=>row.id===id);
  const parts = slot => (data?.catalog.items||[]).filter(row=>row.kind==='part'&&row.role==='part'&&row.rig_id===get('rig').value&&row.slot===slot);
  const isPublished = row => /^\d+$/.test(String(row?.model_asset_id||''));
  function message(value,error=false){get('status').textContent=value;get('status').classList.toggle('error',error);}
  function form(){return {id:get('id').value.trim(),display_name:get('name').value.trim(),rig_id:get('rig').value,
    set_id:get('set').value,parts:Object.fromEntries(slots.map(slot=>[slot,get('slot-'+slot).value])),
    stats:Object.fromEntries(data.stats.statKeys.map(k=>[k,Number(get('stat-'+k).value)]))};}
  function dirty(){return !!data&&(!original||JSON.stringify(form())!==original);}
  function confirmDiscard(){return !dirty()||window.confirm('Discard unsaved character recipe / starting stat changes?');}
  function lock(value){busy=value;get('refresh').disabled=value;get('new').disabled=value;get('reset').disabled=value;updateEditor();}
  async function run(action){if(busy)return;lock(true);try{await action();}catch(error){message(error.message,true);}finally{lock(false);}}
  function setSelect(select,rows,chosen,placeholder='Select…'){
    select.replaceChildren(new Option(placeholder,''));
    for(const row of rows){
      const published=isPublished(row);
      if(row.kind==='set'){select.append(new Option(row.id,row.id));continue;}
      const note=row.kind==='part'?(row.set_id?' · '+row.set_id:'')+(row.gender!=='common'?' · '+row.gender:''):'';
      const status=published?(row.published_revision!==row.revision?' · published old revision':' · published'):' · not published';
      select.append(new Option(row.id+note+status,row.id));
    }
    select.value=chosen||'';
  }
  function chooseParts(values={}){
    const remembered=Object.fromEntries(slots.map(slot=>[slot,values[slot]??get('slot-'+slot).value]));
    for(const slot of slots.filter(s=>s!=='hair'))setSelect(get('slot-'+slot),parts(slot),remembered[slot]);
    const gender=parts('head').find(row=>row.id===get('slot-head').value)?.gender;
    setSelect(get('slot-hair'),parts('hair').filter(row=>row.gender==='common'||row.gender===gender),remembered.hair,
      gender?'Choose '+gender+' / common hair…':'Choose a head first…');
  }
  function fillSets(selectedSet=''){
    const rig=get('rig').value;
    const available=(data.catalog.sets||[]).filter(name=>data.catalog.items.some(row=>row.kind==='part'&&row.rig_id===rig&&row.set_id===name));
    setSelect(get('set'),available.map(id=>({id,kind:'set',model_asset_id:'1'})),selectedSet,'Custom / mixed outfit');
  }
  function applySet(){
    const set=get('set').value;
    for(const slot of clothing)get('slot-'+slot).value=parts(slot).find(row=>row.set_id===set)?.id||'';
    updateEditor();
  }
  function assemblyOutfit(recipe){
    const base=recipe.set_id;
    const mixed=clothing.filter(slot=>recipe.parts[slot]!==base+'_'+slot);
    return !base?'Custom / mixed':mixed.length?base+' · mixed ('+mixed.join(', ')+')':base+' · complete';
  }
  function readinessPreview(payload){
    const catalog=data?.catalog.items||[];
    const rig=catalog.find(row=>row.kind==='rig'&&row.id===payload.rig_id);
    const missing=[];
    if(!rig)missing.push('main rig');else if(!isPublished(rig))missing.push('rig '+rig.id+' publication');
    const head=catalog.find(row=>row.kind==='part'&&row.id===payload.parts.head);
    const gender=head?.gender;
    for(const slot of slots){
      const key=payload.parts[slot];
      const row=catalog.find(r=>r.kind==='part'&&r.id===key&&r.rig_id===payload.rig_id&&r.slot===slot&&r.role==='part');
      if(!row||!key){missing.push(slot+': select a compatible part');continue;}
      if(row.gender!=='common'&&row.gender!==gender)missing.push(slot+': incompatible gender');
      if(!isPublished(row))missing.push(slot+': publish '+key);
      if(row.atlas&&!/^\d+$/.test(String(row.atlas.published_id||'')))missing.push(slot+': atlas not published');
    }
    return missing;
  }
  function updateEditor(){
    if(!data)return;
    const payload=form(),changed=dirty(),missing=readinessPreview(payload);
    get('save').disabled=busy||!changed||!payload.id||!payload.display_name||!payload.rig_id;
    get('save').classList.toggle('character-dirty',changed&&!busy);
    get('editor-summary').textContent=selected
      ? `Editing ${selected} · revision ${editRevision}${changed?' · UNSAVED CHANGES':' · saved'}`
      : 'New character recipe · no model upload or startup switch';
    const groups=clothing.map(slot=>{
      const row=parts(slot).find(item=>item.id===payload.parts[slot]);
      return row?.set_id||'missing';
    });
    const unique=[...new Set(groups)];
    get('mix').textContent=unique.length===1&&unique[0]!=='missing'
      ? `Clothing: complete ${unique[0]} set. Each slot can be replaced independently.`
      : `Clothing: mixed/custom (${clothing.map((s,i)=>s+' = '+groups[i]).join(' · ')}). This is supported.`;
    get('readiness').replaceChildren();
    const lead=node('strong',missing.length?`Draft preview · ${missing.length} dependency issue(s)`:'Draft preview · published IDs present');
    get('readiness').append(lead,node('p',missing.length?missing.join(' · '):'Save to confirm server readiness, bind metadata and atlas versions.'));
    get('readiness').classList.toggle('character-ready',!missing.length);
    get('readiness').classList.toggle('character-needs-publish',!!missing.length);
  }
  function edit(row){
    selected=row.id;editRevision=row.revision;get('id').readOnly=true;
    get('id').value=row.id;get('name').value=row.display_name;get('rig').value=row.assembly.rig_id;
    fillSets(row.assembly.set_id);chooseParts(row.assembly.parts);
    for(const key of data.stats.statKeys)get('stat-'+key).value=row.stats[key];
    original=JSON.stringify(form());updateEditor();
    message(row.assembly_resolved.ready?'Saved · all dependencies are published.':'Saved draft · '+row.assembly_resolved.missing.join(' · '));
  }
  function newDraft(){
    selected=null;editRevision=0;get('id').readOnly=false;
    const keys=new Set(data.items.map(r=>r.id));let id='new_character',i=2;
    while(keys.has(id))id='new_character_'+String(i++).padStart(2,'0');
    get('id').value=id;get('name').value='New Character';
    get('rig').value=data.catalog.items.find(r=>r.kind==='rig'&&r.id==='human')?.id||data.catalog.items.find(r=>r.kind==='rig')?.id||'';
    fillSets((data.catalog.sets||[]).includes('newborn')?'newborn':data.catalog.sets[0]||'');
    chooseParts(Object.fromEntries(slots.map(s=>[s,''])));applySet();
    get('slot-head').value=parts('head').find(p=>p.id==='head_01_male')?.id||parts('head')[0]?.id||'';
    for(const slot of ['eyes','eyebrows'])get('slot-'+slot).value=parts(slot)[0]?.id||'';
    chooseParts();get('slot-hair').value=parts('hair').find(r=>r.id==='hair_02_common')?.id||get('slot-hair').options[1]?.value||'';
    for(const key of data.stats.statKeys)get('stat-'+key).value=data.stats.defaultStats[key];
    original=null;updateEditor();message('New recipe. Save does not publish parts or affect current startup.');
  }
  function render(){
    const host=get('rows');host.replaceChildren();
    for(const row of data.items){
      const tr=document.createElement('tr'),resolved=row.assembly_resolved,ready=resolved.ready;
      if(row.id===selected)tr.classList.add('character-selected-assembly');
      tr.append(node('td',row.display_name+' · '+row.id),node('td',row.assembly.rig_id),node('td',row.assembly.parts.head),
        node('td',assemblyOutfit(row.assembly)),node('td',ready?'READY':`DRAFT · ${resolved.missing.join(' · ')}`));
      const actions=document.createElement('td'),editButton=node('button','Edit recipe');editButton.type='button';
      editButton.onclick=()=>{if(!busy&&confirmDiscard()){
        edit(row);render();
        get('editor-summary').scrollIntoView({behavior:'smooth',block:'start'});
        get('name').focus({preventScroll:true});
      }};actions.append(editButton);
      const start=node('button',data.active_id===row.id?'Startup ✓':'Set as Startup');start.type='button';
      start.disabled=busy||!ready||data.active_id===row.id;
      start.title=ready?'Use for newly spawned characters':resolved.missing.join('\n');
      start.onclick=()=>run(async()=>{
        if(!confirmDiscard())return;
        await post('/api/characters/'+encodeURIComponent(row.id)+'/activate',{});
        await refresh();await loadCharacters();message('Startup set to '+row.id+'. Existing players unchanged; restart Play for a new spawn.');
      });actions.append(start);tr.append(actions);host.append(tr);
    }
  }
  async function refresh(){
    const wasDirty=initialized&&dirty(),previous=selected;
    data=await request(base);
    const rig=get('rig').value;
    setSelect(get('rig'),data.catalog.items.filter(row=>row.kind==='rig'),rig);
    if(!initialized){
      initialized=true;const row=data.items.find(r=>r.id===data.active_id)||data.items[0];
      if(row)edit(row);else newDraft();
    }else if(wasDirty){
      // Never discard edits because a publication finishes or the catalog refreshes.
      fillSets(get('set').value);chooseParts();updateEditor();
      message('Catalog refreshed. Unsaved recipe changes preserved; save will re-check the revision.');
    }else if(previous&&current(previous))edit(current(previous));
    else if(previous){newDraft();message('Selected recipe no longer exists. New draft opened.');}
    else{fillSets(get('set').value);chooseParts();updateEditor();}
    render();
  }
  for(const slot of slots){
    const label=node('label',labels[slot]);const select=document.createElement('select');select.id='ca-slot-'+slot;
    const wrapper=document.createElement('div');wrapper.className='ca-part-control';
    const icon=node('span',icons[slot]);icon.className='ca-part-icon ca-part-'+slot;
    icon.setAttribute('aria-hidden','true');icon.title='Illustrative '+slot+' symbol, not a rendered mesh preview';
    wrapper.append(icon,select);label.append(wrapper);get('parts').append(label);select.onchange=updateEditor;
  }
  get('rig').onchange=()=>{
    fillSets('');chooseParts(Object.fromEntries(slots.map(s=>[s,''])));
    get('slot-head').value=parts('head')[0]?.id||'';chooseParts();updateEditor();
  };
  get('set').onchange=applySet;
  get('slot-head').onchange=()=>{
    const oldHair=get('slot-hair').value;chooseParts();
    if(oldHair&&!get('slot-hair').value)message('Selected hair was incompatible with the new head; choose matching or common hair.');
    updateEditor();
  };
  for(const field of ['id','name'])get(field).addEventListener('input',updateEditor);
  get('new').onclick=()=>{if(data&&!busy&&confirmDiscard()){newDraft();render();}};
  get('reset').onclick=()=>{if(!data||busy)return;const row=current(selected);if(row)edit(row);else newDraft();render();};
  get('refresh').onclick=()=>run(refresh);
  get('save').onclick=()=>run(async()=>{
    const payload={...form(),expected_revision:editRevision};
    const result=await post(base,payload);data=result;
    const saved=current(payload.id);if(saved)edit(saved);
    render();await loadCharacters();
    message('Saved recipe and starting stats · '+(saved.assembly_resolved.ready?'READY for startup.':'DRAFT: publish missing parts before startup.'));
  });
  async function init(){
    data=await request(base);
    for(const key of data.stats.statKeys){
      const label=node('label',key),input=document.createElement('input');input.type='number';input.id='ca-stat-'+key;
      input.min=key==='Level'?'1':'0';input.step='any';if(key==='CritChance')input.max='100';
      label.append(input);get('stats').append(label);input.addEventListener('input',updateEditor);
    }
    await refresh();
  }
  window.addEventListener('character-components-changed',()=>{if(initialized&&!busy)refresh().catch(error=>message(error.message,true));});
  window.game1CharacterAssemblies={
    edit:id=>{const row=current(id);if(row&&!busy&&confirmDiscard()){
      edit(row);render();document.getElementById('character-assemblies-panel').scrollIntoView({behavior:'smooth'});
    }},
    create:()=>{if(data&&!busy&&confirmDiscard()){
      newDraft();render();document.getElementById('character-assemblies-panel').scrollIntoView({behavior:'smooth'});
    }}
  };
  init().catch(error=>message(error.message,true));
})();
