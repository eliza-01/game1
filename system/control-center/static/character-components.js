/* Characters component registration; animations and legacy archetypes are independent. */
(() => {
  const base='/api/characters/components';
  const el=id=>document.getElementById('cp-'+id);
  let catalog=null,plan=null,busy=false,approvalResolve=null,sort={column:'id',ascending:true};
  const post=(url,data={})=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=String(value??'');return node;};
  function status(message,error=false){el('status').textContent=message;el('status').classList.toggle('error',error);}
  // Row dropdowns are recreated by refresh() while an atlas operation is busy.
  // Unlock the *current* DOM controls, not the discarded select that fired onchange.
  function syncAtlasControls(){
    const disabled=busy||!!window.game1CharacterPublications?.isRunning();
    for(const select of el('rows').querySelectorAll('[data-cp-atlas-select]'))select.disabled=disabled;
  }
  function lock(value){
    busy=value;
    const publishing=!!window.game1CharacterPublications?.isRunning();
    el('choose').disabled=value||publishing;
    el('refresh').disabled=value;
    el('register').disabled=value||publishing||!plan;
    window.game1CharacterPublications?.setBusy(value);
    syncAtlasControls();
  }
  function atlasOptions(select,selected='') {
    select.append(new Option('Without atlas / solid material',''));
    for(const group of catalog?.atlas_families||[])for(const v of group.variants||[]) {
      const option=new Option(`${group.atlasKey} · ${v.width}×${v.height}${v.current?'':' · unpublished'}`,v.id);
      option.disabled=!v.current;select.append(option);
    }
    select.value=selected;
  }
  async function run(action){if(busy||window.game1CharacterPublications?.isRunning()){toast('Wait for the current publication queue to finish.',true);return;}lock(true);try{await action();}catch(error){status(error.message,true);}finally{lock(false);}}
  async function refresh(){catalog=await request(base);render();window.dispatchEvent(new Event('character-components-changed'));}
  function render(){
    window.game1CharacterPublications.configure(catalog,busy);
    const host=el('rows');host.replaceChildren();
    for(const button of document.querySelectorAll('[data-cp-sort]')){
      const active=button.dataset.cpSort===sort.column;
      const label={id:'name',slot:'part',set_id:'set'}[button.dataset.cpSort];
      button.textContent=label+(active?(sort.ascending?' ↑':' ↓'):'');
      button.parentElement.setAttribute('aria-sort',active?(sort.ascending?'ascending':'descending'):'none');
    }
    const rowsSorted=[...(catalog.items||[])].sort((a,b)=>{
      const value=row=>String(sort.column==='slot'?(row.kind==='rig'?'rig':row.slot):row[sort.column]||'').toLocaleLowerCase();
      return (sort.ascending?1:-1)*(value(a).localeCompare(value(b))||a.id.localeCompare(b.id));
    });
    for(const row of rowsSorted) {
      const tr=document.createElement('tr');
      const published=!!row.model_asset_id&&row.published_revision===row.revision;
      const issues=[];
      if(!published)issues.push(row.model_asset_id?'New revision is not published':'Model not published');
      if(row.pending_operation)issues.push('Publication pending');
      if(row.kind==='part'&&row.atlas&&(!row.atlas.current||row.atlas.replacementPending))
        issues.push('Bound atlas needs publication');
      const health=text('td',issues.length?'!':'✓');health.className=issues.length?'cp-health-warning':'cp-health-ok';
      health.title=issues.length?issues.join(' · '):'Current publication and dependencies';
      tr.append(health,text('td',row.id),text('td',row.kind==='rig'?'rig':row.role==='effect'?'eyes · effect':row.slot),
        text('td',row.set_id||'—'),text('td',row.rig_id),text('td',`${row.status} · r${row.revision}`),text('td',row.model_asset_id||'—'));
      const atlas=document.createElement('td');
      if(row.kind==='part'){
        const select=document.createElement('select');select.setAttribute('aria-label','Atlas for '+row.id);
        select.dataset.cpAtlasSelect=row.id;
        atlasOptions(select,row.atlas?.variant_id||'');
        // Unbinding is deliberately not inferred from an empty dropdown.
        select.querySelector('option').disabled=!!row.atlas;
        select.disabled=busy||window.game1CharacterPublications.isRunning();
        select.onchange=()=>run(async()=>{
          if(!select.value)return;
          await post(base+'/atlas',{id:row.id,variantId:Number(select.value),expectedRevision:row.atlas?.revision||0});
          await refresh();status('Atlas selected. Shared Image Asset ID reused; no mesh upload.');
        });
        atlas.append(select);
      }else atlas.textContent='—';
      tr.append(atlas);
      const actions=document.createElement('td');
      tr.append(window.game1CharacterPublications.selectionCell(row));
      if(published){const label=text('span','✓ published');label.className='cp-published';actions.append(label);}
      else actions.append(window.game1CharacterPublications.button(row));
      tr.append(actions);host.append(tr);
    }
    window.game1CharacterComponentSummary.render(catalog);
  }
  function preview(){
    const host=el('preview');host.replaceChildren();
    host.append(text('h4','FBX inspection · no registration or upload yet'));
    host.append(text('p',`Rig: ${plan.rig_id} · ${plan.bone_count} bones · ${plan.parts.length} parts`));
    if(plan.partial_required){
      const warning=text('p',`PARTIAL INSPECTION · ${plan.part_errors.length} component error(s): ${plan.part_error}. ${plan.parts.length} valid parts detected, including any rigid hair. Registering these requires explicit approval; rejected meshes will not be extracted or modified.`);
      warning.className='character-preview-warning';host.append(warning);
    }
    if(plan.rig_only_required){
      const warning=text('p',`RIG ONLY · Some FBX parts failed validation: ${plan.part_error}. Only the changed rig can be registered; all existing mesh parts and IDs stay untouched.`);
      warning.className='character-preview-warning';host.append(warning);
    }
    if(plan.rig?.changed){
      const warning=text('p',`RIG REPLACEMENT · ${plan.rig.id} · r${plan.rig.existing_revision} → r${plan.rig.existing_revision+1}. ${plan.rig.warning}. This creates a NEW Model Asset ID on publication. Existing character assemblies stay pinned to the previous published rig; their meshes/animations are not silently migrated.`);
      warning.className='character-preview-warning';host.append(warning);
    }
    if(plan.new_sets.length){
      const sets=text('p','New clothing sets created on Register: '+plan.new_sets.join(', '));
      sets.className='character-preview-warning';host.append(sets);
    }
    if((plan.registered||plan.conflicts).length){
      const warning=text('p',`${(plan.registered||plan.conflicts).length} registered component(s) already exist. They will be KEPT unless you explicitly select Replace for individual rows; published Model IDs remain assigned until any approved replacement is published.`);
      warning.className='character-preview-warning';host.append(warning);
    }
    const newRows=plan.parts.filter(row=>!row.existing_revision);
    if(newRows.length)host.append(text('p',`${newRows.length} NEW component(s) can be registered without replacing any existing parts. After Register they appear in 02 · Component Publication.`));
    for(const row of plan.parts){
      const item=document.createElement('div');item.className='character-preview-row';
      item.append(text('strong',row.id),text('span',
        `${row.slot}${row.role==='effect'?' · effect (not a default face slot)':''}${row.set_id?' · set '+row.set_id:''}${row.attachment_mode==='pivot'?' · rigid pivot → hair_mount':''} · ${row.triangles} tris · `+
        (row.published_asset_id?'published · replacement approval needed':row.existing_revision?'already registered':'new component')));
      host.append(item);
    }
    host.append(text('p','Register extracts independent source FBX files. Use the publication queue afterwards; saving a character recipe is a separate step.'));
  }
  function approve(){
    const newRows=plan.parts.filter(row=>!row.existing_revision);
    const dlg=el('conflict');el('conflicts').replaceChildren();
    if(newRows.length){
      el('conflicts').append(text('p','ADD NEW COMPONENTS · checked by default'));
      for(const row of newRows){
        const label=document.createElement('label');const check=document.createElement('input');
        check.type='checkbox';check.value=row.id;check.dataset.newPart='1';check.checked=true;
        label.append(check,document.createTextNode(` Add NEW ${row.id} · ${row.slot}${row.attachment_mode==='pivot'?' · pivot → hair_mount':''}`));
        el('conflicts').append(label);
      }
    }
    if(plan.rig?.changed){
      const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.value='rig:'+plan.rig.id;
      label.append(check,document.createTextNode(` Replace RIG ${plan.rig.id} · ${plan.rig.warning} · publish as NEW Model Asset (old ID retained until success)`));
      el('conflicts').append(label);
    }
    if(plan.rig?.changed && ((plan.registered||plan.conflicts).length||plan.rig_only_required||plan.partial_required)){
      const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.dataset.rigOnly='1';check.checked=!newRows.length;check.disabled=!!plan.rig_only_required;
      label.append(check,document.createTextNode(plan.rig_only_required
        ? ' Rig only required · FBX parts have errors; keep all existing mesh components and IDs'
        : ' Rig only · keep all existing mesh components and published IDs unchanged'));
      el('conflicts').append(label);
    }
    if(plan.partial_required){
      const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.dataset.partialApproval='1';
      label.append(check,document.createTextNode(` Register ONLY ${plan.parts.length} validated components; skip ${plan.part_errors.length} invalid component(s) shown in Inspect`));
      el('conflicts').append(label);
    }
    if((plan.registered||plan.conflicts).length)el('conflicts').append(text('p','REPLACE REGISTERED COMPONENTS · optional, unchecked by default'));
    for(const row of plan.registered||plan.conflicts){
      const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.value=row.id;check.dataset.meshApproval='1';
      label.append(check,document.createTextNode(` Replace ${row.id} · ${row.published_asset_id?'published '+row.published_asset_id:'registered r'+row.existing_revision}${row.content_unchanged?' · mesh content is unchanged':''}`));
      el('conflicts').append(label);
    }
    const validate=()=>{
      const rig=el('conflicts').querySelector('input[value^="rig:"]');
      const only=el('conflicts').querySelector('[data-rig-only]');
      const meshes=[...el('conflicts').querySelectorAll('[data-mesh-approval]')];
      const newParts=[...el('conflicts').querySelectorAll('[data-new-part]')];
      const partial=el('conflicts').querySelector('[data-partial-approval]');
      if(partial)partial.disabled=!!only?.checked;
      for(const check of [...meshes,...newParts])check.disabled=!!only?.checked;
      const validRig=!rig||rig.checked;
      const hasSelection=!!only?.checked||meshes.some(check=>check.checked)||newParts.some(check=>check.checked)||!!rig?.checked;
      const validPartial=!!only?.checked||!partial||partial.checked;
      el('confirm').disabled=!(validRig&&hasSelection&&validPartial);
    };
    for(const checkbox of el('conflicts').querySelectorAll('input'))checkbox.onchange=validate;
    validate();dlg.showModal();
    return new Promise(resolve=>{approvalResolve=resolve;});
  }
  function finishApproval(value){el('conflict').close();const resolve=approvalResolve;approvalResolve=null;resolve?.(value);}
  el('cancel').onclick=()=>finishApproval(null);
  el('conflict').addEventListener('cancel',event=>{event.preventDefault();finishApproval(null);});
  el('confirm').onclick=()=>{
    const only=!!el('conflicts').querySelector('[data-rig-only]:checked');
    const checked=selector=>[...el('conflicts').querySelectorAll(selector)].filter(input=>input.checked).map(input=>input.value);
    finishApproval({replacements:only?[]:checked('[data-mesh-approval]'),newParts:only?[]:checked('[data-new-part]'),
      replaceRig:!!el('conflicts').querySelector('input[value^="rig:"]:checked'),rigOnly:only,
      allowPartial:!!el('conflicts').querySelector('[data-partial-approval]:checked')&&!only});
  };
  el('choose').onclick=()=>run(async()=>{
    const picked=await post('/api/files/choose-character-model');if(!picked.path)return;
    plan=null;el('preview').replaceChildren();el('source').textContent=picked.path;status('Reading FBX mesh names and rig…');
    plan=await post(base+'/inspect',{sourcePath:picked.path});preview();
    status('Inspection complete. Review the parts and any new sets before registering. Nothing has been changed or uploaded.');
    if(plan.parts.length||plan.rig?.changed||plan.partial_required)plan.approvals=await approve();
    if(plan.approvals===null)status('Registration cancelled. No components were modified.');
  });
  el('register').onclick=()=>run(async()=>{
    const approval=plan.approvals??await approve();if(approval===null){status('Cancelled. No components were modified.');return;}
    status('Registering approved rig revision and extracting component FBX files…');
    await post(base+'/register',{token:plan.token,replacements:approval.replacements,newParts:approval.newParts,replaceRig:approval.replaceRig,rigOnly:approval.rigOnly,allowPartial:approval.allowPartial||false});plan=null;el('preview').replaceChildren();
    await refresh();status('Registration complete. Previous published IDs are preserved until publication succeeds. No Roblox Model Asset was uploaded during registration. Select the changed rig and parts in step 02 to publish NEW Model Asset IDs.');
  });
  el('refresh').onclick=()=>run(async()=>{await refresh();status('Catalog refreshed.');});
  for(const button of document.querySelectorAll('[data-cp-sort]')){
    button.onclick=()=>{
      const column=button.dataset.cpSort;
      sort=sort.column===column?{column,ascending:!sort.ascending}:{column,ascending:true};
      render();
    };
  }
  window.addEventListener('character-publication-state',()=>lock(busy));
  window.addEventListener('character-publication-updated',()=>refresh().catch(error=>status(error.message,true)));
  refresh().catch(error=>status(error.message,true));
})();
