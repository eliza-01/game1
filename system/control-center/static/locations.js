(()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function toast(message,bad=false){const node=$('toast');if(!node)return;node.textContent=message;node.className='toast show'+(bad?' error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.className='toast',5200)}
  const view=$('locations-view');
  if(!view)return;

  view.innerHTML=`
    <div class="panel hero location-hero">
      <div><span class="eyebrow">polygon location registry · studio authoring</span><h2>locations</h2><p>Author map regions in Studio and keep them registered as project data.</p></div>
      <div class="metrics"><div><b id="location-count">0</b><span>registered</span></div><div><b id="location-synced">0</b><span>studio synced</span></div><div><b id="location-stale">0</b><span>stale / error</span></div></div>
    </div>
    <div class="location-workflow">
      <aside class="panel location-card location-sidebar">
        <div class="section-title"><div><span>polygon locations</span><h3>registry</h3></div><span id="location-list-count">0</span></div>
        <p class="location-sidebar-intro">Saved gameplay regions. Select one to edit or create a new contour in Studio.</p>
        <div class="location-search-block">
          <label class="location-field location-search-field"><span>Search</span><input id="location-search" type="search" placeholder="Name or Location ID"></label>
          <div class="location-toolbar"><button id="location-restore" type="button">restore markers</button><button id="location-validate" type="button">validate</button><button id="location-refresh" type="button">refresh</button></div>
        </div>
        <div class="location-list-header"><strong>Locations</strong><span>project registry</span></div>
        <div id="location-records" class="location-list"><div class="location-empty">No registered locations yet.</div></div>
        <details class="naming-guide location-manifest"><summary>registry paths</summary><div id="location-manifest-info" class="details"></div></details>
      </aside>
      <section class="panel location-card location-editor">
        <div class="section-title"><div><span>location editor</span><h3>location polygon</h3></div><span id="location-state" class="location-state draft">DRAFT</span></div>
        <p class="location-editor-intro">Draw the contour in Studio, verify it here, then save it into the project registry.</p>

        <div class="location-editor-section">
          <div class="location-section-heading"><div><span>identity</span><strong>Location details</strong></div><small>Name is editable. IDs are assigned by the authoring flow.</small></div>
          <div class="location-editor-grid">
            <label class="location-field location-field-name"><span>Location name</span><input id="location-name" maxlength="80" placeholder="Starting Village"></label>
            <label class="location-field"><span>Location ID</span><input id="location-id" readonly placeholder="Created when drawing"></label>
            <label class="location-field"><span>Roblox Place ID</span><input id="location-place-id" type="number" readonly value="0"></label>
          </div>
        </div>

        <div class="location-editor-section">
          <div class="location-section-heading"><div><span>geometry</span><strong>Studio contour</strong></div><small>Click surfaces in contour order. After point 3, click the first orange vertex to close. Esc cancels.</small></div>
          <div id="location-geometry" class="location-geometry">
            <div class="location-geometry-summary"><div><strong id="location-geometry-title">contour not set</strong><small id="location-geometry-hint">At least 3 points are required.</small></div><span id="location-point-badge" class="location-point-badge">0 POINTS</span></div>
            <details><summary>point coordinates</summary><div id="location-points" class="location-points">—</div></details>
          </div>
        </div>

        <div class="location-action-zone">
          <div class="location-primary-actions"><button id="location-draw" class="primary" type="button">draw in Studio</button><button id="location-save" type="button">save location</button></div>
          <div class="location-secondary-actions"><button id="location-select" type="button" disabled>select in Studio</button><button id="location-new" type="button">new location</button><button id="location-delete" class="danger" type="button" disabled>delete</button></div>
        </div>
        <div id="location-operation" class="status-box location-operation"><strong>ready</strong><span>Draw the first location in Studio.</span></div>
      </section>
    </div>`;

  let state={records:[],recordCount:0,manifestPath:'',registryPath:''};
  let selectedId='';
  let points=[];
  let busy=false;

  async function request(path,body){
    const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
    const response=await fetch(path,options);let data={};try{data=await response.json()}catch{}
    if(!response.ok)throw Error(data.error||`http ${response.status}`);return data;
  }
  function current(){return state.records.find(row=>row.locationId===selectedId)||null}
  function payload(){return {locationId:$('location-id').value.trim(),name:$('location-name').value.trim(),placeId:Number($('location-place-id').value||0),points:points.map(p=>({...p}))}}
  function setOperation(title,text,bad=false){const node=$('location-operation');node.className='status-box'+(bad?' error':'');node.innerHTML=`<strong>${esc(title)}</strong><span>${esc(text)}</span>`}
  function setEditorState(value){const stateName=String(value||'draft').toLowerCase();const node=$('location-state');node.textContent=stateName.toUpperCase();node.className='location-state '+stateName}
  function markDirty(){setEditorState(selectedId?'edited':'draft')}
  function resetDraft(){selectedId='';points=[];$('location-id').value='';$('location-name').value='';$('location-place-id').value='0';setEditorState('draft');setOperation('new location','draw a closed polygon in Studio.');render()}
  function applyRecord(row,draft=false){selectedId=draft?'':String(row.locationId||'');$('location-id').value=String(row.locationId||'');$('location-name').value=String(row.name||'');$('location-place-id').value=Number(row.placeId||0);points=(row.points||[]).map(p=>({x:Number(p.x),y:Number(p.y),z:Number(p.z)}));setEditorState(draft?'draft':(row.syncState||'stale'));render()}
  function renderGeometry(){const count=points.length;const ready=count>=3;const geometry=$('location-geometry');geometry.classList.toggle('ready',ready);$('location-point-badge').textContent=`${count} ${count===1?'POINT':'POINTS'}`;$('location-geometry-title').textContent=ready?'closed polygon':(count?'unfinished contour':'contour not set');$('location-geometry-hint').textContent=ready?'Contour is ready to save. Runtime uses X/Z; Y is kept for Studio markers.':'At least 3 points are required. Close it by clicking the first point in Studio.';$('location-points').innerHTML=count?points.map((p,index)=>`${String(index+1).padStart(2,'0')} · X ${Number(p.x).toFixed(2)} · Y ${Number(p.y).toFixed(2)} · Z ${Number(p.z).toFixed(2)}`).join('<br>'):'—'}
  function renderRecords(){const query=$('location-search').value.trim().toLowerCase();const rows=(state.records||[]).filter(row=>!query||String(row.name||'').toLowerCase().includes(query)||String(row.locationId||'').toLowerCase().includes(query));$('location-list-count').textContent=String(rows.length);$('location-records').innerHTML=rows.length?rows.map(row=>`<button type="button" class="location-record ${row.locationId===selectedId?'active':''}" data-location-id="${esc(row.locationId)}"><span><strong>${esc(row.name)}</strong><small>${esc(row.locationId)} · ${Number(row.pointCount||row.points?.length||0)} points · Place ${Number(row.placeId||0)}</small></span><i class="${esc(row.syncState||'stale')}">${esc(String(row.syncState||'stale').toUpperCase())}</i></button>`).join(''):'<div class="location-empty">No locations match this search.</div>';$('location-records').querySelectorAll('[data-location-id]').forEach(node=>{node.disabled=busy;node.onclick=()=>{const row=state.records.find(item=>item.locationId===node.dataset.locationId);if(row){applyRecord(row);const error=row.studioSync?.error||'';setOperation(error?'studio sync error':'location loaded',error||'polygon loaded from the project registry.',!!error)}}})}
  function renderMetrics(){const rows=state.records||[];$('location-count').textContent=String(rows.length);$('location-synced').textContent=String(rows.filter(row=>row.syncState==='synced').length);$('location-stale').textContent=String(rows.filter(row=>row.syncState!=='synced').length);$('location-manifest-info').innerHTML=`<dl><div><dt>manifest</dt><dd>${esc(state.manifestPath||'—')}</dd></div><div><dt>runtime registry</dt><dd>${esc(state.registryPath||'—')}</dd></div><div><dt>records</dt><dd>${rows.length}</dd></div></dl>`}
  function render(){renderGeometry();renderRecords();renderMetrics();const row=current();$('location-select').disabled=busy||!row;$('location-delete').disabled=busy||!row;$('location-draw').disabled=busy;$('location-save').disabled=busy||points.length<3||!$('location-name').value.trim()||!$('location-id').value.trim();$('location-new').disabled=busy;$('location-restore').disabled=busy;$('location-validate').disabled=busy;$('location-refresh').disabled=busy}
  async function refresh(preserve=true){const draft=preserve?payload():null;const selected=preserve?selectedId:'';state=await request('/api/locations');if(preserve&&draft&&draft.locationId&&!state.records.some(row=>row.locationId===selected)){selectedId=selected;$('location-id').value=draft.locationId;$('location-name').value=draft.name;$('location-place-id').value=draft.placeId;points=draft.points}else if(selected){const row=state.records.find(item=>item.locationId===selected);if(row)applyRecord(row)}render()}
  async function run(title,text,fn){if(busy)return;busy=true;render();setOperation(title,text||'working…');try{return await fn()}catch(error){setOperation('error',error.message,true);toast(error.message,true);return null}finally{busy=false;render()}}

  $('location-name').addEventListener('input',()=>{markDirty();render()});
  $('location-search').addEventListener('input',renderRecords);
  $('location-draw').onclick=()=>run('Studio drawing','Place vertices; click the first point to close.',async()=>{const result=await request('/api/locations/draw',payload());applyRecord(result.draft,true);$('location-id').value=result.draft.locationId;setEditorState('draft');setOperation('contour ready',`${points.length} points received from Studio. Save the location.`);toast('Location contour received from Studio.')});
  $('location-save').onclick=()=>run('saving location','writing manifest, runtime registry and Studio marker…',async()=>{const result=await request('/api/locations/register',payload());selectedId=result.record.locationId;await refresh(false);applyRecord(state.records.find(row=>row.locationId===selectedId)||result.record);const ok=result.record.syncState==='synced';const detail=result.studio?.skipped?'Studio marker already current.':(result.studio?.error||'Studio marker synchronized.');setOperation(ok?'location saved':'location saved · studio stale',detail,!ok);toast(ok?'Location saved.':'Location saved, but Studio sync failed.',!ok)});
  $('location-select').onclick=()=>run('selecting location','focusing marker in Studio…',async()=>{await request('/api/locations/select',{locationId:selectedId});setOperation('selected','Studio marker selected and camera focused.')});
  $('location-new').onclick=resetDraft;
  $('location-delete').onclick=()=>{const row=current();if(!row||!confirm(`Delete location “${row.name}”?`))return;run('deleting location','removing registry record and Studio marker…',async()=>{await request('/api/locations/delete',{locationId:row.locationId});resetDraft();await refresh(false);setOperation('deleted','Location removed.');toast('Location deleted.')})};
  $('location-restore').onclick=()=>run('restoring markers','rebuilding all project-owned Location markers in Studio…',async()=>{const result=await request('/api/locations/restore',{});await refresh(false);setOperation('markers restored',`${result.recordCount} location marker(s) synchronized.`);toast('Location markers restored.')});
  $('location-validate').onclick=()=>run('validating registry','checking polygons and generated runtime data…',async()=>{const result=await request('/api/locations/validate',{});setOperation('registry valid',`${result.recordCount} location record(s); runtime registry current.`);toast('Location registry valid.')});
  $('location-refresh').onclick=()=>refresh(false).catch(error=>toast(error.message,true));

  window.game1LocationsLoad=()=>refresh(false).catch(error=>{setOperation('error',error.message,true);toast(error.message,true)});
})();
