/* M234 · Shared consumer atlas editor. One Atlas Registry, one UI for Real Estate
 * mesh parts and Location Assets. Attaching is not selecting, selecting is not
 * publishing, and neither operation changes Studio without explicit Sync.
 */
window.game1ConsumerAtlasEditor = (() => {
  const colors = ['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'];
  const html = value => esc(String(value ?? ''));
  const newState = () => ({search:'',picker:false,busy:false,pending:null,publicationOfferId:0});
  const variants = catalog => (catalog||[]).flatMap(group =>
    (group.variants||[]).map(v => ({...v,atlasKey:group.atlasKey})));
  const available = catalog => variants(catalog).filter(v => v.current && v.published_id && !v.retired);
  function render(state,{currentId=0,linked=[],catalog=[],busy=false,openPublish=false,offerPublication=false}={}){
    const active=Number(currentId||0);
    const selected=variants(catalog).find(v=>Number(v.id)===active)||
      linked.find(v=>Number(v.id)===active)||null;
    const attached=new Map();
    for(const v of linked)attached.set(Number(v.id),v);
    if(selected)attached.set(active,selected);
    const dots=[...attached.values()].sort((a,b)=>
      Number(b.width||0)*Number(b.height||0)-Number(a.width||0)*Number(a.height||0));
    const choices=available(catalog).filter(v=>
      (!state.search||`${v.filename} ${v.atlasKey} ${v.resolution} ${v.published_id}`.toLowerCase().includes(state.search.toLowerCase()))
      && !attached.has(Number(v.id)));
    const disabled=busy||state.busy;
    const unpublished=selected&&!selected.retired&&!selected.published_id;
    const offer=dots.find(v=>Number(v.id)===Number(state.publicationOfferId)&&
      !v.retired&&!v.published_id)||null;
    const current=selected?`${html(selected.filename)} · ${html(selected.resolution)} · Image ID ${html(selected.published_id||'not published')}`:
      'No atlas selected';
    return `<section class="real-estate-mesh-step shared-atlas-editor" aria-label="Atlas variants">
        <div class="real-estate-mesh-step-head"><strong>Attached atlases</strong><span class="real-estate-step-status ${selected?.current?'ready':'pending'}">${selected?.current?'Published':unpublished?'Publish required':selected?'Review required':'Choose atlas'}</span></div>
        <div class="shared-atlas-current">${current}</div>
        <div class="deco-atlas-dots" role="group" aria-label="Attached atlas variants">${dots.map((v,i)=>{
          const on=Number(v.id)===active;
          const tip=`${v.filename} · ${v.resolution} · Image ID ${v.published_id||'unpublished'}`;
          const unpublishedOffer=offerPublication&&!v.retired&&!v.published_id;
          const label=unpublishedOffer?`${tip} · Нажмите, чтобы предложить публикацию`:tip;
          return `<button type="button" class="deco-atlas-dot ${on?'is-active':''}" style="--dot-color:${colors[i%colors.length]}" data-ca-choice="${Number(v.id)}" aria-label="${html(label)}" title="${html(label)}" aria-pressed="${on}" ${disabled||(!v.current&&!unpublishedOffer&&!(openPublish&&on&&!v.published_id))?'disabled':''} ${unpublishedOffer?'data-ca-offer-publication':openPublish&&on&&!v.published_id?'data-ca-open-publish':''}><span></span></button>`;
        }).join('')}</div>
        <small>Switch published variants by clicking a dot. No automatic Studio Sync.</small>
        ${offerPublication&&offer?`<div class="shared-atlas-publication-offer" role="group" aria-label="Публикация атласа">
          <strong>Опубликовать атлас?</strong>
          <small>${html(offer.filename)} · ${html(offer.resolution)} · Image ID ещё нет</small>
          <small>Roblox создаст новый Image ID. Активный атлас и Studio не изменятся.</small>
          <div class="actions"><button type="button" data-ca-publish-offer ${disabled?'disabled':''}>Опубликовать атлас</button><button type="button" data-ca-cancel-offer ${disabled?'disabled':''}>Отмена</button></div>
        </div>`:''}
        ${unpublished&&openPublish&&!offerPublication?`<div class="shared-atlas-unpublished"><span>Atlas registered · Image ID not published</span><button type="button" data-ca-open-publish>Publish this atlas</button></div>`:''}
        <div class="actions"><button type="button" data-ca-toggle ${disabled?'disabled':''}>Connect existing atlas</button><button type="button" data-ca-upload ${disabled?'disabled':''}>Upload new atlas</button></div>
        ${state.picker?`<div class="shared-atlas-picker"><label>Search all published atlases<input type="search" data-ca-search value="${html(state.search)}" placeholder="Filename · resolution · Image ID"></label>
          <div class="shared-atlas-choices">${choices.length?choices.map(v=>`<button type="button" data-ca-attach="${Number(v.id)}" ${disabled?'disabled':''}><strong>${html(v.filename)}</strong><small>${html(v.resolution)} · ${html(v.published_id)}</small></button>`).join(''):'<small>No published, unattached atlases match the search.</small>'}</div></div>`:''}
        ${state.pending?`<div class="shared-atlas-preview" role="group" aria-label="Atlas upload preview">
          <strong>${state.pending.existing?'Replace shared atlas publication':'Register and publish new atlas'}</strong>
          <small>${html(state.pending.filename)} · ${html(state.pending.width)}×${html(state.pending.height)}</small>
          <div class="shared-atlas-compare"><figure>${state.pending.oldPreview?`<img src="${state.pending.oldPreview}" alt="Existing atlas pixels">`:'<span>No previous image</span>'}<figcaption>Current · Image ID ${html(state.pending.existing?.publishedId||'—')}</figcaption></figure>
          <figure><img src="${state.pending.newPreview||''}" alt="Selected atlas pixels"><figcaption>Selected file · ${html(state.pending.filename)}</figcaption></figure></div>
          ${!state.pending.valid?`<small class="real-estate-step-status issue">${html(state.pending.reason)}</small>`:''}
          ${state.pending.replacementRequired?`<label class="shared-atlas-approval"><input type="checkbox" data-ca-approval ${state.pending.approved?'checked':''}> I understand this replaces a shared Image ID for every consumer. Studio Sync is manual.</label>`:''}
          <div class="actions"><button type="button" data-ca-confirm ${disabled||!state.pending.valid||(state.pending.replacementRequired&&!state.pending.approved)?'disabled':''}>${state.pending.unchanged?'Use unchanged published atlas':state.pending.existing?'Confirm replacement and publish':'Publish and connect atlas'}</button><button type="button" data-ca-cancel ${disabled?'disabled':''}>Cancel</button></div>
        </div>`:''}
      </section>`;
  }
  // Host passes domain identity and its own refresh/status callbacks. Neither
  // this module nor the Atlas Registry assumes anything about model geometry.
  function wire(container,state,opts){
    const find = selector=>container.querySelector(selector);
    const consumer = {consumerType:opts.consumerType,slug:opts.slug,part:opts.part||''};
    const requestChoice=(action,id)=>request('/api/texture-atlases/consumer-choice',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...consumer,action,variantId:id,expectedRevision:Number(opts.getRevision?.() ?? opts.revision ?? 0)}),
    });
    async function run(label,action){
      if(state.busy||opts.busy)return;
      state.busy=true;opts.onMessage(`${label}…`);opts.onRender();
      try{ const result=await action();await opts.onRefresh();return result; }
      catch(error){opts.onMessage(error?.message||String(error),true);return null;}
      finally{state.busy=false;opts.onRender();}
    }
    const toggle=find('[data-ca-toggle]');if(toggle)toggle.onclick=()=>{state.picker=!state.picker;opts.onRender();};
    const input=find('[data-ca-search]');if(input)input.oninput=()=>{
      state.search=input.value;const offset=input.selectionStart;opts.onRender();
      const next=find('[data-ca-search]');next?.focus();try{next?.setSelectionRange(offset,offset);}catch{}
    };
    for(const b of container.querySelectorAll('[data-ca-choice]'))b.onclick=()=>{
      if(b.hasAttribute('data-ca-offer-publication')){
        state.publicationOfferId=Number(b.dataset.caChoice);
        opts.onRender();
        return;
      }
      if(b.hasAttribute('data-ca-open-publish'))return opts.onOpenPublish?.();
      state.publicationOfferId=0;
      return run('Switching atlas',async()=>{
        await requestChoice('select',Number(b.dataset.caChoice));opts.onMessage('Active atlas changed. Sync Studio explicitly when ready.');
      });
    };
    const offered=find('[data-ca-publish-offer]');if(offered)offered.onclick=async()=>{
      const id=Number(state.publicationOfferId);
      if(!id||!opts.onPublishAtlas)return;
      const success=await opts.onPublishAtlas(id);
      if(success)state.publicationOfferId=0;
      opts.onRender();
    };
    const dismiss=find('[data-ca-cancel-offer]');if(dismiss)dismiss.onclick=()=>{
      state.publicationOfferId=0;opts.onRender();
    };
    for(const b of container.querySelectorAll('.shared-atlas-unpublished [data-ca-open-publish]'))
      b.onclick=()=>opts.onOpenPublish?.();
    for(const b of container.querySelectorAll('[data-ca-attach]'))b.onclick=()=>run('Attaching atlas',async()=>{
      await requestChoice('attach',Number(b.dataset.caAttach));state.picker=false;
      opts.onMessage('Atlas attached. Select its dot to make it active; no Studio Sync performed.');
    });
    const upload=find('[data-ca-upload]');if(upload)upload.onclick=()=>run('Inspecting selected image',async()=>{
      const chosen=await window.game1AtlasWorkflow.chooseImage(opts.filePicker);
      if(chosen?.path){
        state.pending=await request('/api/texture-atlases/preview-source',{
          method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sourcePath:chosen.path})});
        state.pending.approved=false;state.picker=false;
        opts.onMessage('Compare existing and selected images. Nothing has been saved or uploaded.');
      }else opts.onMessage('Image selection cancelled.');
    });
    const approval=find('[data-ca-approval]');if(approval)approval.onchange=()=>{
      state.pending.approved=approval.checked;opts.onRender();
    };
    const cancel=find('[data-ca-cancel]');if(cancel)cancel.onclick=()=>{state.pending=null;opts.onRender();};
    const confirm=find('[data-ca-confirm]');if(confirm)confirm.onclick=()=>run('Publishing reviewed atlas',async()=>{
      const plan=state.pending;if(!plan?.valid)return;
      if(plan.replacementRequired&&!plan.approved)throw Error('Explicit shared atlas replacement approval is required');
      const result=await request('/api/texture-atlases/publish-reviewed',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          sourcePath:plan.sourcePath,sha256:plan.sha256,
          expectedVariantId:plan.existing?.id||0,
          expectedPublishedId:plan.existing?.publishedId||'',
          approveReplacement:Boolean(plan.approved),
        }),
      });
      // New variants become available immediately; existing selected variants
      // keep the same binding ID while their publication revision changes.
      await requestChoice('attach',Number(result.variant.id));
      await opts.onRefresh(); // publication may increment every consumer binding revision
      if(Number(opts.getCurrentId?.()||0)!==Number(result.variant.id))
        await requestChoice('select',Number(result.variant.id));
      state.pending=null;
      const warnings = (result.exportWarnings||[]).join(' | ');
      opts.onMessage((result.unchanged?'Existing image unchanged; active atlas selected.':
        `Atlas published · Image ID ${result.publishedAssetId}. Other consumers require manual Studio Sync.`) +
        (warnings?` WARNING: ${warnings}`:''),Boolean(warnings));
    });
  }
  return Object.freeze({newState,render,wire});
})();
