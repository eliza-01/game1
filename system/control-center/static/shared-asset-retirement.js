/* Reusable, explicit retirement preview for Location Assets and Real Estate.
 * The default removes only the selected registration and keeps shared images.
 * No decisions are inferred from HTML lists or stale table state.
 */
(() => {
  let dialog;
  function ensureDialog(){
    if(dialog)return dialog;
    dialog=document.createElement('dialog');
    dialog.id='shared-asset-retirement-dialog';
    dialog.className='shared-asset-retirement-dialog';
    dialog.innerHTML=`<h3>Delete registration · shared assets</h3>
      <p data-retirement-target></p>
      <p class="hint">Model registrations can be deleted without deleting shared Image Assets or their source files.</p>
      <div data-retirement-dependencies class="shared-asset-retirement-dependencies"></div>
      <div class="shared-asset-retirement-modes">
        <label><input type="radio" name="shared-retirement-mode" value="preserve" checked> <b>Keep used assets (recommended)</b><small>Delete only this registration. Shared textures, Image Asset IDs and dependent models remain available.</small></label>
        <label><input type="radio" name="shared-retirement-mode" value="all"> <b>Delete linked registrations</b><small>Only for structural dependencies; shared atlas consumers are never deletion targets.</small></label>
      </div>
      <label data-retirement-confirm-label hidden>Type the registration slug to confirm deleting all dependents:
        <input type="text" data-retirement-confirm autocomplete="off" spellcheck="false"></label>
      <div data-retirement-error role="alert"></div>
      <div class="actions"><button type="button" data-retirement-cancel>Cancel</button>
        <button type="button" class="danger" data-retirement-submit>Delete</button></div>`;
    document.body.appendChild(dialog);
    return dialog;
  }
  async function open({kind,slug,onDone}){
    const d=ensureDialog();
    const target=d.querySelector('[data-retirement-target]');
    const deps=d.querySelector('[data-retirement-dependencies]');
    const error=d.querySelector('[data-retirement-error]');
    const confirm=d.querySelector('[data-retirement-confirm]');
    const confirmLabel=d.querySelector('[data-retirement-confirm-label]');
    const submit=d.querySelector('[data-retirement-submit]');
    const modes=[...d.querySelectorAll('[name="shared-retirement-mode"]')];
    target.textContent=`Loading shared references for ${kind} / ${slug}…`;
    deps.replaceChildren();error.textContent='';confirm.value='';
    modes[0].checked=true;modes[1].checked=false;confirmLabel.hidden=true;submit.disabled=true;
    d.querySelector('[data-retirement-cancel]').onclick=()=>d.close();
    d.showModal();
    let plan;
    try{
      plan=await request(`/api/asset-retirement/impact?kind=${encodeURIComponent(kind)}&slug=${encodeURIComponent(slug)}`);
    }catch(exc){error.textContent=exc.message;return;}
    if(!d.open)return;
    target.textContent=`${kind==='estate'?'Real Estate':'Location Asset'} · ${slug}`;
    const count=plan.dependentCount||0;
    const summary=document.createElement('p');
    const shareCount=(plan.sharedAtlasUses||[]).reduce((n,item)=>n+(item.uses||[]).length,0);
    summary.textContent=count?`${count} legacy dependent registration(s) use shared textures:`:
      shareCount?`Shared Image Assets are also used by ${shareCount} other part(s). Those registrations will be preserved.`:
      'No other model registrations depend on this asset.';
    deps.appendChild(summary);
    if(count||shareCount){
      // Group by Image Asset identity, NOT by the first model that published it.
      // A single image may be referenced by multiple legacy owners/part names.
      const sources=new Map();
      const owners=new Map((plan.nodes||[]).map(node=>[`${node.kind}:${node.slug}`,node]));
      for(const relation of plan.relations||[]){
        const sourcePart=relation.ownerPart||'texture';
        const owner=owners.get(relation.owner);
        const texture=relation.owner.startsWith('estate:')?owner?.textures?.[sourcePart]:null;
        const assetId=String(texture?.assetId||owner?.textureId||'');
        const filename=texture?.filename||owner?.textureFilename||'';
        const atlasKey=texture?.atlasKey||owner?.atlasKey||'';
        const identity=window.game1AtlasIdentity.describe({filename,atlasKey});
        const key=assetId?`image:${assetId}`:`reference:${relation.owner}:${sourcePart}`;
        if(!sources.has(key))sources.set(key,{assetId,identity,uses:[]});
        const group=sources.get(key);
        if(!group.uses.some(use=>use.dependent===relation.dependent&&use.part===relation.part)){
          group.uses.push({dependent:relation.dependent,part:relation.part});
        }
      }
      // Independently bound Atlas Registry consumers are NOT cascade targets.
      // Show them in the same image-based grouping as legacy references.
      for(const shared of plan.sharedAtlasUses||[]){
        const assetId=String(shared.assetId||'');
        const key=assetId?`image:${assetId}`:`variant:${shared.variantId}`;
        if(!sources.has(key))sources.set(key,{assetId,
          identity:window.game1AtlasIdentity.describe({filename:shared.filename,atlasKey:shared.atlasKey}),uses:[]});
        const group=sources.get(key);
        for(const use of shared.uses||[]){
          if(!group.uses.some(item=>item.dependent===use.dependent&&item.part===use.part))
            group.uses.push({dependent:use.dependent,part:use.part});
        }
      }
      for(const source of [...sources.values()].sort((a,b)=>
        a.identity.key.localeCompare(b.identity.key)||a.assetId.localeCompare(b.assetId))){
        const section=document.createElement('section');
        section.className='shared-asset-retirement-source';
        const heading=document.createElement('h4');
        heading.textContent=`Shared atlas · ${source.identity.key}`;
        section.appendChild(heading);
        const description=document.createElement('p');
        description.className='shared-asset-retirement-source-id';
        description.textContent=[
          source.identity.variant?`${source.identity.name} · variant ${source.identity.variant}`:source.identity.name,
          source.identity.resolution,
          source.assetId?`Image Asset ID: ${source.assetId}`:'Image Asset ID unavailable'
        ].filter(Boolean).join(' · ');
        section.appendChild(description);
        const consumerModels=new Set(source.uses.map(use=>use.dependent)).size;
        const summary=document.createElement('p');
        summary.className='shared-asset-retirement-source-summary';
        summary.textContent=`Used by ${source.uses.length} part(s) in ${consumerModels} registration(s):`;
        section.appendChild(summary);
        const list=document.createElement('ul');
        source.uses.sort((a,b)=>a.dependent.localeCompare(b.dependent)||a.part.localeCompare(b.part));
        for(const use of source.uses){
          const li=document.createElement('li');
          li.textContent=`${use.dependent} / ${use.part}`;
          list.appendChild(li);
        }
        section.appendChild(list);
        deps.appendChild(section);
      }
    }
    modes[1].disabled=count===0;
    const update=()=>{
      const all=modes[1].checked;
      confirmLabel.hidden=!all||count===0;
      submit.textContent=all&&count>0
        ?`Delete all (${plan.nodes.length} registrations)`
        :`${kind==='estate'?'Delete house':'Delete location asset'}${count>0||shareCount>0?' · keep shared assets':''}`;
      submit.disabled=all&&count>0&&confirm.value!==slug;
    };
    modes.forEach(r=>r.onchange=update);
    confirm.oninput=update;
    update();
    submit.onclick=async()=>{
      const mode=modes.find(r=>r.checked)?.value||'preserve';
      if(mode==='all'&&count>0&&confirm.value!==slug)return;
      submit.disabled=true;error.textContent='';
      try{
        const result=await request('/api/asset-retirement/execute',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({kind,slug,mode,token:plan.token})
        });
        d.close();
        await onDone(result);
      }catch(exc){error.textContent=exc.message;update();}
    };
  }
  window.game1AssetRetirement={open};
})();
