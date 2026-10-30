/* Character atlas dialog and scoped catalog. No global Location/Real Estate atlas controls. */
(() => {
  const base='/api/characters/components/atlases';
  const el=id=>document.getElementById('cp-atlas-'+id);
  const post=(url,data={})=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  let catalog=null,inspection=null,busy=false;
  const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=String(value??'');return node;};
  const dialog=el('dialog');
  function report(message,error=false){el('report').textContent=message;el('report').classList.toggle('error',error);}
  function stage(message){el('stages').append(text('div',message));}
  function lock(value){busy=value;el('register').disabled=value;el('reselect').disabled=value;el('close').disabled=value;syncActions();}
  function syncActions(){
    const can=inspection?.valid&&!inspection?.unchanged;
    el('confirm').disabled=busy||!can||(inspection?.replacementRequired&&!el('approval').checked);
  }
  function renderTable(){
    const host=el('rows');host.replaceChildren();
    const groups=catalog?.atlas_families||[];
    for(const group of groups)for(const v of group.variants||[]){
      const tr=document.createElement('tr');
      const state=v.replacementPending?'Replacement staged':v.current?'✓ published':v.published_id?'Outdated':'Not published';
      tr.append(text('td',group.atlasKey),text('td',`${v.width}×${v.height}`),text('td',v.published_id||'—'));
      const cell=text('td',state);cell.className=v.current&&!v.replacementPending?'cp-health-ok':'cp-health-warning';
      tr.append(cell);host.append(tr);
    }
    if(!host.children.length){const tr=document.createElement('tr');const empty=text('td','No Character atlases yet. Register an atlas to begin.');empty.colSpan=4;tr.append(empty);host.append(tr);}
  }
  async function refresh(){catalog=await request('/api/characters/components');renderTable();}
  function show(inspectionData){
    inspection=inspectionData;el('stages').replaceChildren();el('approval').checked=false;
    const existing=inspection?.existing;
    el('title').textContent=inspection.valid?(existing?'Review Character atlas replacement':'Review new Character atlas'):'Atlas needs a valid filename';
    el('old-preview').src=inspection.oldPreview||'';el('old-preview').hidden=!inspection.oldPreview;
    el('new-preview').src=inspection.newPreview||'';
    el('info').textContent=`${inspection.filename} · ${inspection.width}×${inspection.height}`+
      (existing?` · existing Image Asset ${existing.publishedId||'not published'}`:' · new Character atlas');
    el('validation').textContent=inspection.reason||'';
    el('validation').hidden=!!inspection.valid;
    el('expected').textContent=inspection.valid?'':'Expected filename: '+inspection.expectedFilename;
    el('show-folder').hidden=!!inspection.valid;
    el('approval-label').hidden=!inspection.replacementRequired;
    el('confirm').textContent=inspection.replacementRequired?'Confirm replacement & publish':'Publish atlas';
    if(!inspection.valid)report('Rename the file in its folder, then choose it again. Nothing was registered or uploaded.',true);
    else if(inspection.unchanged)report('Already published · unchanged pixels. No upload required. Done!');
    else report(existing?'Compare old and new atlases, then approve publication.':'Review the selected atlas, then publish.');
    syncActions();
    if(!dialog.open)dialog.showModal();
  }
  async function choose(){
    if(busy)return;
    try{
      const picked=await post('/api/files/choose-character-atlas');
      if(!picked.path)return;
      // Inspect on Host Agent. File bytes never appear as a local-file URL in the browser.
      show(await post(base+'/inspect',{sourcePath:picked.path}));
    }catch(error){report(error.message,true);if(!dialog.open)dialog.showModal();}
  }
  async function publish(){
    if(busy||!inspection?.valid||inspection.unchanged)return;
    if(inspection.replacementRequired&&!el('approval').checked)return;
    lock(true);el('stages').replaceChildren();
    stage('✓ Preview and filename checked');
    stage('… Registering source revision and publishing Roblox Image Asset');
    report('Publishing… Leave this dialog open until the server responds.');
    try{
      const result=await post(base+'/publish',{
        sourcePath:inspection.sourcePath,sha256:inspection.sha256,
        expectedVariantId:inspection.existing?.id||0,
        expectedPublishedId:inspection.existing?.publishedId||'',
        approveReplacement:!!el('approval').checked
      });
      stage('✓ Registry and Image Asset publication committed');
      stage('✓ Character manifest exported');
      stage(`Done! Roblox Image Asset ID: ${result.publishedAssetId}`);
      report(result.previousAssetId&&result.previousAssetId!==result.publishedAssetId
        ?`Done! ${result.previousAssetId} → ${result.publishedAssetId}. Close this dialog when ready.`
        :`Done! Image Asset ${result.publishedAssetId}. Close this dialog when ready.`);
      inspection.unchanged=true;await refresh();
      window.dispatchEvent(new Event('character-components-changed'));
    }catch(error){
      stage('! Publication or export needs attention — '+error.message);
      report('Not completed: '+error.message+' · review the status before retrying. No automatic upload retry.',true);
      // Require a new inspection after ambiguity (e.g. upload succeeded, response lost).
      inspection=null;
    }finally{lock(false);}
  }
  el('register').onclick=choose;
  el('reselect').onclick=choose;
  el('confirm').onclick=publish;
  el('approval').onchange=syncActions;
  el('close').onclick=()=>{if(!busy)dialog.close();};
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  el('show-folder').onclick=async()=>{
    if(!inspection||busy)return;
    try{await post(base+'/reveal',{sourcePath:inspection.sourcePath});}
    catch(error){report(error.message,true);}
  };
  window.addEventListener('character-components-changed',()=>refresh().catch(error=>report(error.message,true)));
  refresh().catch(error=>report(error.message,true));
})();
