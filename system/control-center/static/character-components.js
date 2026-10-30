/* Characters component registration; animations and legacy archetypes are independent. */
(() => {
  const base='/api/characters/components';
  const el=id=>document.getElementById('cp-'+id);
  let catalog=null,plan=null,busy=false,approvalResolve=null,sort={column:'id',ascending:true};
  const post=(url,data={})=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=String(value??'');return node;};
  function status(message,error=false){el('status').textContent=message;el('status').classList.toggle('error',error);}
  function lock(value){busy=value;const publishing=window.game1CharacterPublications?.isRunning();el('choose').disabled=value||publishing;el('refresh').disabled=value;el('register').disabled=value||publishing||!plan;window.game1CharacterPublications?.setBusy(value);}
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
    const rows=catalog.items||[];
    el('sets').textContent=(catalog.sets||[]).length?'Registered clothing sets: '+catalog.sets.join(', '):'No clothing sets yet. A part named <set>_upper/lower/gloves/boots automatically registers its set.';
    const rigs=rows.filter(row=>row.kind==='rig').length;
    const published=rows.filter(row=>row.published_revision===row.revision&&row.model_asset_id).length;
    const awaiting=rows.filter(row=>row.published_revision!==row.revision).length;
    el('counts').textContent=`${rigs} rig(s) · ${rows.length-rigs} reusable part(s)`;
    el('flow-summary').textContent=`${(catalog.sets||[]).length} set(s) · ${published}/${rows.length} current Model Assets · ${awaiting} component(s) awaiting publication. Published revisions remain assigned during replacement. Select only the changes you want to upload.`;
  }
  function preview(){
    const host=el('preview');host.replaceChildren();
    host.append(text('h4','FBX inspection · no registration or upload yet'));
    host.append(text('p',`Rig: ${plan.rig_id} · ${plan.bone_count} bones · ${plan.parts.length} parts`));
    if(plan.new_sets.length){
      const sets=text('p','New clothing sets created on Register: '+plan.new_sets.join(', '));
      sets.className='character-preview-warning';host.append(sets);
    }
    if(plan.conflicts.length){
      const warning=text('p',`${plan.conflicts.length} published component(s) have matching names. Replacements require individual confirmation; their old Model IDs remain assigned until new publication succeeds.`);
      warning.className='character-preview-warning';host.append(warning);
    }
    for(const row of plan.parts){
      const item=document.createElement('div');item.className='character-preview-row';
      item.append(text('strong',row.id),text('span',
        `${row.slot}${row.role==='effect'?' · effect (not a default face slot)':''}${row.set_id?' · set '+row.set_id:''} · ${row.triangles} tris · `+
        (row.published_asset_id?'published · replacement approval needed':row.existing_revision?'already registered':'new component')));
      host.append(item);
    }
    host.append(text('p','Register extracts independent source FBX files. Use the publication queue afterwards; saving a character recipe is a separate step.'));
  }
  function approve(){
    if(!plan.conflicts.length)return Promise.resolve([]);
    const dlg=el('conflict');el('conflicts').replaceChildren();
    for(const row of plan.conflicts){
      const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.value=row.id;
      label.append(check,document.createTextNode(` Replace ${row.id} · published ${row.published_asset_id}${row.content_unchanged?' · mesh content is unchanged':''}`));
      check.onchange=()=>{el('confirm').disabled=el('conflicts').querySelectorAll('input:checked').length!==plan.conflicts.length;};
      el('conflicts').append(label);
    }
    el('confirm').disabled=true;dlg.showModal();
    return new Promise(resolve=>{approvalResolve=resolve;});
  }
  function finishApproval(value){el('conflict').close();const resolve=approvalResolve;approvalResolve=null;resolve?.(value);}
  el('cancel').onclick=()=>finishApproval(null);
  el('conflict').addEventListener('cancel',event=>{event.preventDefault();finishApproval(null);});
  el('confirm').onclick=()=>finishApproval([...el('conflicts').querySelectorAll('input:checked')].map(n=>n.value));
  el('choose').onclick=()=>run(async()=>{
    const picked=await post('/api/files/choose-character-model');if(!picked.path)return;
    plan=null;el('preview').replaceChildren();el('source').textContent=picked.path;status('Reading FBX mesh names and rig…');
    plan=await post(base+'/inspect',{sourcePath:picked.path});preview();
    status('Inspection complete. Review the parts and any new sets before registering. Nothing has been changed or uploaded.');
    if(plan.conflicts.length)plan.confirmed_replacements=await approve();
  });
  el('register').onclick=()=>run(async()=>{
    const replacements=plan.confirmed_replacements??await approve();if(replacements===null){status('Cancelled. Exclude unchanged published meshes from FBX, then choose it again.');return;}
    status('Registering rig and extracting component FBX files…');
    await post(base+'/register',{token:plan.token,replacements});plan=null;el('preview').replaceChildren();
    await refresh();status('Registration complete. Newly named sets are now in the catalog; existing missing parts were preserved. No Roblox Model Asset was uploaded. Select changed components in step 02.');
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
