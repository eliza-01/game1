/* Shared progress UI for one component and a selected batch. No upload logic. */
(() => {
  const base='/api/characters/components/publication-queue';
  const el=id=>document.getElementById('cp-'+id);
  const selected=new Set();let catalog=null,uiBusy=false,job=null,timer=null,polling=false,toastAnchor=null;
  const storageKey='game1.character.publicationQueue.v1',noticeKey=storageKey+'.notified';
  const active=()=>!!job&&['queued','running'].includes(job.status);
  const key=row=>row.kind+':'+row.id;
  const eligible=row=>row.published_revision!==row.revision;
  const rows=()=>catalog?.items||[];
  const make=(tag,value)=>{const n=document.createElement(tag);n.textContent=String(value??'');return n;};
  function remember(id){try{if(id)localStorage.setItem(storageKey,id);else localStorage.removeItem(storageKey);}catch{}}
  function controls(){
    const available=rows().filter(eligible),keys=new Set(available.map(key));
    for(const value of selected)if(!keys.has(value))selected.delete(value);
    const all=el('publish-select-all');all.disabled=uiBusy||active()||!available.length;
    all.checked=!!available.length&&available.every(row=>selected.has(key(row)));
    all.indeterminate=!!selected.size&&!all.checked;
    el('publish-all').disabled=uiBusy||active()||!selected.size||!catalog?.publication?.configured;
    el('publish-count').textContent=selected.size+' selected';
    for(const checkbox of document.querySelectorAll('[data-cp-publish-select]')){
      const row=rows().find(r=>key(r)===checkbox.dataset.cpPublishSelect);
      checkbox.disabled=uiBusy||active()||!row||!eligible(row);checkbox.checked=selected.has(checkbox.dataset.cpPublishSelect);
    }
    for(const button of document.querySelectorAll('[data-cp-publish-button]')){
      const row=rows().find(r=>key(r)===button.dataset.cpPublishButton);
      button.disabled=uiBusy||active()||!row||!eligible(row)||!catalog?.publication?.configured;
    }
    el('publication-open').hidden=!job;
  }
  function selectionCell(row){
    const td=document.createElement('td');td.className='cp-publish-selection';
    const input=document.createElement('input');input.type='checkbox';input.dataset.cpPublishSelect=key(row);
    input.setAttribute('aria-label','Select '+row.id+' for publication');
    input.checked=selected.has(key(row));input.disabled=uiBusy||active()||!eligible(row);
    input.onchange=()=>{if(input.checked)selected.add(key(row));else selected.delete(key(row));controls();};
    td.append(input);return td;
  }
  function button(row){
    const b=make('button',row.pending_operation?'Resume publication':row.status==='replacement_pending'?'Publish replacement':'Publish');
    b.type='button';b.dataset.cpPublishButton=key(row);
    b.disabled=uiBusy||active()||!eligible(row)||!catalog?.publication?.configured;
    b.onclick=()=>start([row]);return b;
  }
  function renderJob(){
    const host=el('publication-rows');host.replaceChildren();if(!job)return;
    const done=job.items.filter(i=>['succeeded','skipped','failed','interrupted'].includes(i.status)).length;
    el('publication-progress').max=job.items.length;el('publication-progress').value=done;
    el('publication-summary').textContent=`${done} / ${job.items.length} completed · ${job.status.replaceAll('_',' ')}`;
    for(const item of job.items){
      const tr=document.createElement('tr');tr.className='cp-publication-'+item.status;
      tr.append(make('td',item.id),make('td',item.status),make('td',item.error||item.warning||item.step),make('td',item.asset_id||'—'));host.append(tr);
    }
    controls();window.dispatchEvent(new Event('character-publication-state'));
  }
  function open(){
    const dlg=el('publication-dialog'),notice=document.getElementById('toast');
    // A normal z-index cannot rise above a modal's top layer. Keep the shared
    // toast visible/dismissible inside this dialog, restoring its home on close.
    if(notice&&!dlg.contains(notice)){
      toastAnchor=document.createComment('publication-toast-home');notice.before(toastAnchor);dlg.append(notice);
    }
    if(!dlg.open)dlg.showModal();
  }
  function notify(){
    if(!job||active())return;
    try{if(sessionStorage.getItem(noticeKey)===job.id)return;sessionStorage.setItem(noticeKey,job.id);}catch{}
    const good=job.items.filter(i=>i.status==='succeeded').length,skipped=job.items.filter(i=>i.status==='skipped').length;
    const bad=job.items.filter(i=>i.status==='failed'||i.status==='interrupted').length;
    const warning=job.items.some(i=>i.warning);
    const item=job.items[0];
    const message=job.items.length===1
      ? (item.error||item.warning?`${item.id}: ${item.error||item.warning}`:(item.status==='succeeded'?`Published ${item.id} · Model Asset ${item.asset_id}`:item.status==='skipped'?`${item.id} is already published.`:`${item.id}: ${item.step}`))
      : `Publication queue: ${good} published, ${skipped} already current, ${bad} failed/interrupted${warning?' · refresh needs attention':''}.`;
    toast(message,bad>0||warning);window.dispatchEvent(new Event('character-publication-updated'));
  }
  function later(delay=1200){clearTimeout(timer);if(active())timer=setTimeout(poll,delay);}
  async function poll(){
    if(!job||polling)return;polling=true;
    try{
      const data=await request(base+'/'+encodeURIComponent(job.id));
      const previous=JSON.stringify(job.items);job=data.job;renderJob();
      if(previous!==JSON.stringify(job.items))window.dispatchEvent(new Event('character-publication-updated'));
      if(!active())notify();
    }catch(error){
      if(error.message==='publication queue not found'){
        job.status='interrupted';for(const item of job.items)if(['queued','publishing'].includes(item.status)){item.status='interrupted';item.step='Saved queue unavailable. Refresh component statuses before retrying.';}
        renderJob();notify();
      }else el('publication-summary').textContent='Connection lost. The queue may still be running. Reconnecting… '+error.message;
    }
    finally{polling=false;later();}
  }
  async function start(items){
    if(uiBusy||active())return;
    const id=crypto.randomUUID();
    job={schema_version:1,id,status:'queued',items:items.map(row=>({kind:row.kind,id:row.id,revision:row.revision,status:'queued',step:'Starting queue',asset_id:'',error:'',warning:''}))};
    remember(id);renderJob();open();
    try{
      job=await request(base,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:id,items:job.items.map(({kind,id,revision})=>({kind,id,revision}))})});
      renderJob();if(active())later(100);else notify();
    }catch(error){
      // A lost POST response is not evidence that Roblox upload failed.
      try{job=(await request(base+'/'+id)).job;renderJob();if(active())later(100);else notify();}
      catch{
        job.status='failed';for(const item of job.items){item.status='failed';item.error=error.message;}
        remember(null);renderJob();notify();
      }
    }
  }
  el('publish-select-all').onchange=event=>{if(uiBusy||active())return;for(const row of rows().filter(eligible)){if(event.target.checked)selected.add(key(row));else selected.delete(key(row));}controls();};
  el('publish-all').onclick=()=>start(rows().filter(row=>selected.has(key(row))&&eligible(row)));
  el('publication-open').onclick=open;el('publication-close').onclick=()=>el('publication-dialog').close();
  el('publication-dialog').addEventListener('close',()=>{
    const notice=document.getElementById('toast');if(toastAnchor?.parentNode&&notice)toastAnchor.replaceWith(notice);toastAnchor=null;
  });
  // Closing the dialog intentionally does not cancel the server worker.
  window.game1CharacterPublications={selectionCell,button,isRunning:active,setBusy:value=>{uiBusy=value;controls();},configure:(data,value)=>{catalog=data;uiBusy=value;controls();}};
  (async()=>{
    let id='';try{id=localStorage.getItem(storageKey)||'';}catch{}
    let data;
    try{data=await request(id?base+'/'+encodeURIComponent(id):base);}catch{data=await request(base);}
    if(job||!data.job)return;
    job=data.job;remember(job.id);renderJob();
    if(active()){open();later(100);}else if(id)notify();
  })().catch(error=>{toast('Cannot restore publication queue: '+error.message,true);});
})();
