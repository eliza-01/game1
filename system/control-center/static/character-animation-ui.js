/* Character animation profile presentation and explicit review/replacement workflows. */
(function(){
  const $=id=>document.getElementById(id);
  const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const missingKey='game1.animations.showMissing';
  let api, sortKey='context', sortDir=1, showMissing=false, nameQuery='', scan=null, replacing=null, replacementPath='', busy=false;
  let manualConfirmAsset="",manualConfirmChecked=false, commonQuery='', commonSelection='';
  let timelineByClip=null; // null means the separate timeline registry has not been checked
  try{showMissing=localStorage.getItem(missingKey)==='1'}catch{}
  function pendingRows(){
    const data=api.state().animations||{}, items=data.items||[], catalog=data.filenameRules||[];
    if(!showMissing)return items.concat(data.inherited||[]);
    const present=items.concat(data.inherited||[]);
    const missing=catalog.filter(def=>def.context!=='common'&&!present.some(row=>row.scope===def.scope&&context(row)===def.context&&row.slot===def.state&&Number(row.variant||0)===1)).map(def=>({
      scope:def.scope,weapon_set:(['base','emotions','social'].includes(def.context))?'':def.context,slot:def.state,variant:1,
      name:def.canonicalFilename,source_path:'',status:'MISSING',missing:true,weight:0,binding_id:null,asset_id:''}));
    return present.concat(missing);
  }
  function context(row){return row.scope==='weapon'?(row.weapon_set||row.weaponSet):row.scope}
  function searchMatch(row){
    if(!nameQuery)return true;
    const haystack=[row.name,row.slot,row.source_path,row.scope,context(row)].join(' ').toLocaleLowerCase();
    return haystack.includes(nameQuery);
  }
  function sortedRows(){const s=api.state(), items=pendingRows().filter(row=>(s.animationFilter==='all'||((['base','emotions','social'].includes(s.animationFilter))?row.scope===s.animationFilter:row.scope==='weapon'&&row.weapon_set===s.animationFilter.replace('weapon:','')))&&searchMatch(row));
    const key=row=>sortKey==='context'?context(row):sortKey==='variant'?Number(row.variant||0):String(row[sortKey]||'').toLowerCase();
    return items.sort((a,b)=>{const av=key(a),bv=key(b);const compare=typeof av==='number'?av-bv:String(av).localeCompare(String(bv),'ru',{numeric:true});return sortDir*compare||context(a).localeCompare(context(b))||String(a.slot).localeCompare(String(b.slot))||Number(a.variant||0)-Number(b.variant||0)});
  }
  function renderCommonPicker(){
    const data=api.state().animations||{};
    const select=$('animation-common-select'), button=$('animation-common-assign');
    if(!select||!button)return;
    const candidates=data.sharedCandidates||[];
    const filtered=candidates.filter(row=>!commonQuery||
      [row.name,row.scope,row.slot,row.weaponSet,row.sourceCharacter,row.sourceGender,row.assetId]
        .join(' ').toLocaleLowerCase().includes(commonQuery));
    select.replaceChildren();
    for(const row of filtered){
      const option=document.createElement('option');
      option.value=row.bindingId;
      option.disabled=!row.ready;
      option.title=row.reason||row.name;
      option.textContent=`${row.selected?'✓ ':''}${row.scope}${row.scope==='weapon'?'/'+row.weaponSet:''} · ${row.slot}${row.variant?' #'+row.variant:''} · ${row.sourceGender} · ${row.assetId}${row.ready?'':' · '+row.reason}`;
      select.append(option);
    }
    if(filtered.some(row=>row.bindingId===commonSelection))select.value=commonSelection;
    else{
      commonSelection='';
      select.selectedIndex=-1;
    }
    const selected=candidates.find(row=>row.bindingId===commonSelection);
    button.disabled=busy||api.state().animationPublishing||!selected||!selected.ready||selected.selected;
    button.textContent=selected?.replacesSource&&!selected?.selected?'заменить источник common':'назначить common';
    $('animation-common-details').textContent=selected
      ?`${selected.sourceCharacter} · ${selected.name} · ${selected.assetId} · ${selected.ready?selected.compatibility:'недоступно: '+selected.reason}${selected.selected?' · уже common':''}`
      :`${filtered.length} опубликованных анимаций · несовместимые варианты недоступны для выбора`;
  }
  function renderShared(){
    const data=api.state().animations||{}, host=$('animation-shared-rows');
    if(!host)return;
    const sharedRows=(data.shared||[]).map(row=>`<div class="animation-scan-item"><span><b>${safe(row.scope)} · ${safe(row.slot)}_${String(row.variant||1).padStart(2,'0')}</b><small>${safe(row.sourceFilename||row.source_character)} · ${safe(row.asset_id||'—')} · ${safe(row.status)}${row.sourceFilename?' · общий клип имеет приоритет':''}</small></span><button type="button" data-shared-remove="${safe(row.source_binding_id)}">отменить common</button></div>`).join('');
    const pendingRows=(data.commonPending||[]).map(row=>`<div class="animation-scan-item"><span><b>human_common · ${safe(row.name)}</b><small>${safe(row.status)} · ${safe(row.clip_id)} · публикация требуется</small></span>${row.status==='LOCAL_ONLY'?`<button type="button" data-common-publish="${safe(row.clip_id)}" ${api.state().animationPublishing?'disabled':''}>publish</button>`:'<small>Replace из исходного профиля</small>'}</div>`).join('');
    host.innerHTML=sharedRows+pendingRows||'<p class="muted">Общих анимаций пока нет.</p>';
    host.querySelectorAll('[data-shared-remove]').forEach(btn=>btn.onclick=()=>setCommon(btn.dataset.sharedRemove,false));
    host.querySelectorAll('[data-common-publish]').forEach(btn=>btn.onclick=()=>api.publish(btn.dataset.commonPublish));
    renderCommonPicker();
    document.querySelectorAll('[data-animation-gender]').forEach(btn=>{
      const char=(data.characters||[]).find(c=>c.id===api.state().animationCharacter);
      btn.classList.toggle('active',char?.gender===btn.dataset.animationGender);
    });
  }
  async function setCommon(bindingId,enabled){
    if(busy)return;
    busy=true;renderCommonPicker();
    try{
      await api.request('/api/animations/shared',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bindingId,enabled})});
      await api.load();
    }catch(e){api.toast(e.message,true);}finally{busy=false;renderCommonPicker();}
  }
  function renderRows(){const s=api.state(), host=$('animation-rows');host.replaceChildren();$('animation-filter-label').textContent=s.animationFilter.replace('weapon:','');
    renderShared();
    for(const row of sortedRows()){
      const attack= !row.missing && row.slot==='attack' && !!row.asset_id && !row.document_only;
      const timing=attack&&timelineByClip?.get(row.clip_id);
      const timingLabel=timelineByClip===null?'таймлайн: не проверен':timing?.configured?'таймлайн: готов':'таймлайн: нужен HitEnd';
      const tr=document.createElement('tr');tr.className=(row.binding_id&&row.binding_id===s.animationSelected?'active ':'')+(row.missing?'animation-empty-row':'');
      tr.innerHTML=`<td><span class="context-chip ${safe(row.scope)}">${safe(context(row))}</span></td><td><b>${safe(row.slot)}_${String(row.variant||1).padStart(2,'0')}</b></td><td>${row.variant?String(row.variant).padStart(2,'0'):'—'}</td><td>${safe(row.name||'—')}${row.source_path?`<br><small class="animation-source-path" title="${safe(row.source_path)}">${safe(row.source_path)}</small>`:''}</td><td>${safe(row.asset_id||'—')}</td><td><span class="tag ${safe(String(row.status).toLowerCase())}">${safe(row.status)}</span>${row.overriddenByCommon?'<small>common активен · эта личная анимация сохранена</small>':''}${row.user_attested?'<small class="animation-timeline-status required">Replaced · user attested, not verified</small>':''}${attack?`<small class="animation-timeline-status ${timing?.configured?'ready':'required'}">${safe(timingLabel)}</small>`:''}</td><td>${row.missing||row.inherited?'—':`<input data-weight class="weight-input" type="number" min="1" max="10000" value="${safe(row.weight||100)}">`}</td><td>${row.missing?'Требуется файл':row.inherited?`common · ${safe(row.sourceCharacter)} · read only`:`<div class="row-actions"><button data-open>детали</button>${row.document_only?'программное состояние':row.asset_id?`<button data-replace>${row.status==='CHANGED'?'проверить / replace':'replace'}</button>`:`<button data-publish ${row.status==='LOCAL_ONLY'&&!api.state().animationPublishing?'':'disabled'}>publish</button>`}${row.asset_id?`<button data-share type="button">common</button>`:''}${attack?'<button data-timeline type="button">таймлайн удара</button>':''}<button data-delete class="danger">удалить</button></div>`}</td>`;
      if(!row.missing&&!row.inherited){tr.querySelector('[data-open]').onclick=()=>{s.animationSelected=row.binding_id;api.render()};tr.querySelector('[data-weight]').onchange=e=>api.weight(row.binding_id,e.target.value);tr.querySelector('[data-publish]')?.addEventListener('click',()=>api.publish(row.clip_id));tr.querySelector('[data-replace]')?.addEventListener('click',()=>openReplacement(row));tr.querySelector('[data-timeline]')?.addEventListener('click',()=>api.openTimeline(row.clip_id));tr.querySelector('[data-share]')?.addEventListener('click',()=>setCommon(row.binding_id,true));tr.querySelector('[data-delete]').onclick=()=>api.remove(row.binding_id)}
      tr.dataset.context=context(row);tr.dataset.slot=row.slot;host.append(tr);
    }
    if(!host.children.length)host.innerHTML='<tr><td colspan="8" class="muted">'+(nameQuery?'Ничего не найдено. Измени запрос или сбрось поиск.':'Нет анимаций в этом разделе.')+'</td></tr>';
    for(const th of document.querySelectorAll('[data-animation-sort]')){const active=th.dataset.animationSort===sortKey;th.setAttribute('aria-sort',active?(sortDir===1?'ascending':'descending'):'none');th.classList.toggle('animation-sort-active',active);th.textContent=th.dataset.animationSort+(active?(sortDir===1?' ↑':' ↓'):' ↕')}
  }
  async function refreshAttackTimelines(){
    if(!api)return;
    try{
      const snapshot=await api.request('/api/timelines');
      timelineByClip=new Map((snapshot.items||[]).map(row=>[row.clipId,row]));
    }catch{
      timelineByClip=null; // network errors cannot be interpreted as a missing timeline
    }
    renderRows();
  }
  function renderRules(){const host=$('animation-filename-rules'), data=api.state().animations||{}, rules=data.filenameRules||[];
    const sets=['base','emotions','social',...(data.weaponSets||[])];host.innerHTML=sets.map(context=>{const rows=rules.filter(r=>r.context===context);if(!rows.length)return '';return `<section class="filename-rule-group"><div class="filename-rule-context">${safe(context)}</div><div class="filename-rule-table"><div class="filename-rule-head"><span>state</span><span>canonical filename</span><span>variant</span></div>${rows.map(r=>`<button class="filename-rule-row animation-rule-link" data-context="${safe(context)}" data-slot="${safe(r.state)}" type="button"><code>${safe(r.state)}</code><code>${safe(r.canonicalFilename)}</code><span>${r.variants?safe(r.variantPattern||'01..n'):'—'}</span></button>`).join('')}</div></section>`}).join('');
    host.querySelectorAll('.animation-rule-link').forEach(b=>b.addEventListener('click',()=>jump(b.dataset.context,b.dataset.slot)));
  }
  function jump(context,slot){nameQuery='';$('animation-name-search').value='';const s=api.state();s.animationFilter=(['base','emotions','social'].includes(context))?context:'weapon:'+context;showMissing=true;$('animation-show-missing').checked=true;try{localStorage.setItem(missingKey,'1')}catch{}api.render();const row=[...$('animation-rows').querySelectorAll('tr')].find(r=>r.dataset.context===context&&r.dataset.slot===slot);if(row){row.classList.add('animation-jump-focus');row.scrollIntoView({behavior:'smooth',block:'center'});row.querySelector('[data-open]')?.click()}else $('animation-profile-panel').scrollIntoView({behavior:'smooth',block:'start'});}
  const open=id=>{const d=$(id);if(!d.open)d.showModal()};
  function syncScanPublishButton(){
    const selected=scan&&scan.characterId===api.state().animationCharacter&&
      [...$('animation-scan-review').querySelectorAll('[data-review-index]:checked')]
        .some(input=>scan.items?.[Number(input.dataset.reviewIndex)]?.selectable);
    $('animation-register-selected').disabled=busy||!selected;
  }
  function renderScan(){const host=$('animation-scan-review');if(!scan)return;const items=scan.items||[];
    const count=x=>items.filter(r=>r.status===x).length;
    host.innerHTML=`<p><strong>${safe(scan.characterId)}</strong> · ${scan.filesScanned} файлов · ${count('NEW')} новых · ${count('UNCHANGED')} без изменений · ${count('REPLACE_REQUIRED')} требуют Replace · ${(scan.unassigned||[]).length} с неверными именами</p><p class="animation-info">Папка может содержать Male, Female и human_common. Файл направляется в профиль по префиксу имени; Common публикуется один раз. Опубликованные клипы заменяются только через их строку.</p><div class="animation-scan-list">${items.map((row,index)=>`<label class="animation-scan-item"><input type="checkbox" data-review-index="${index}" ${row.selectable?'checked':'disabled'}><span><strong>${safe(row.filename)}</strong><small>${safe(row.common?'common · male + female':row.ownerCharacterId+' · '+context(row))} / ${safe(row.slot)} ${row.variant?'· '+row.variant:''}</small></span><span class="animation-review-status ${row.status==='NEW'?'new':''}">${safe(row.status)}</span></label>`).join('')}${(scan.unassigned||[]).map(row=>`<div class="animation-scan-item animation-invalid"><span><strong>${safe(row.filename)}</strong><small>${safe(row.reason)}</small></span><span>Неверное имя</span></div>`).join('')}</div><div class="animation-review-result" id="animation-review-result" aria-live="polite"></div>`;
    syncScanPublishButton();
  }
  async function scanFolder(){if(busy||api.state().animationPublishing)return;const s=api.state();const characterId=s.animationCharacter;const path=$('animation-folder-path').value.trim();if(!path||!characterId){api.toast('Выбери персонажа и папку',true);return;}busy=true;scan=null;syncScanPublishButton();$('scan-animations').disabled=true;
    try{
      const preview=await api.request('/api/animations/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({characterId,rootPath:path})});
      if(api.state().animationCharacter!==characterId){api.toast('Персонаж изменился во время сканирования. Повтори Scan folder.',true);return;}
      scan=preview;renderScan();open('animation-scan-dialog');$('animation-scan-status').innerHTML=`<strong>Проверено ${scan.filesScanned} файлов</strong><span>Открой отчёт сканирования и выбери новые анимации.</span>`;
    }catch(e){api.toast(e.message,true)}finally{busy=false;syncScanPublishButton();api.render()}
  }
  async function registerSelected(){
    if(!scan||busy||api.state().animationPublishing)return;
    if(scan.characterId!==api.state().animationCharacter){api.toast('Выбран другой персонаж. Повтори Scan folder.',true);syncScanPublishButton();return;}
    const items=[...$('animation-scan-review').querySelectorAll('[data-review-index]:checked')]
      .map(input=>scan.items?.[Number(input.dataset.reviewIndex)]).filter(row=>row?.selectable);
    if(!items.length){syncScanPublishButton();return;}
    busy=true;syncScanPublishButton();let registered=0,committed=false;const report=$('animation-review-result');report.innerHTML='';
    try{
      const result=await api.request('/api/animations/register-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({characterId:scan.characterId,rootPath:scan.rootPath,items:items.map(r=>({path:r.path,sha256:r.sha256,documentSha256:r.documentSha256||''}))})});
      registered=result.count;committed=true;
      report.textContent=`Зарегистрировано: ${registered}. Очередь публикации отображается над таблицей.`;
      const summary=await window.game1AnimationPublishQueue.publishRegistered(result.registered||[]);
      report.textContent=`Зарегистрировано: ${registered} · опубликовано: ${summary.published} · документов: ${summary.documents}. `+
        (summary.failed?'Ошибка публикации — смотри очередь. Неопубликованные клипы сохранены.':'Очередь завершена.');
    }catch(e){report.textContent='Не выполнено: '+e.message;api.toast(e.message,true)}
    finally{busy=false;if(committed)scan=null;syncScanPublishButton();api.render()}
  }

  function syncManualConfirm(){
    const el=$('animation-replace-manual');if(!el)return;
    el.disabled=busy||replacing?.status!=='CHANGED'||
      !manualConfirmChecked||manualConfirmAsset!==String(replacing?.asset_id||'');
  }
  function renderReplacement(){const row=replacing,el=$('animation-replace-review');if(!row)return;
    el.innerHTML=`<p><b>${safe(row.name)}</b> · ${safe(context(row))} / ${safe(row.slot)}</p>`+
      `<p>Permanent Roblox Asset ID: <strong>${safe(row.asset_id)}</strong>. It does not change.</p>`+
      `<p class="animation-info">1. Choose the new .rbxm/.rbxmx and stage it. 2. In Studio replace the existing Roblox animation under the SAME ID. 3. Verify through Roblox, or explicitly attest to a completed replacement below.</p>`+
      `<p>Staged file: <b>${safe(replacementPath||'not selected')}</b></p>`+
      (row.status==='CHANGED'?`<div class="animation-manual-confirm"><strong>Manual confirmation · no Open Cloud verification</strong>`+
        `<label>Type the permanent Asset ID<input type="text" data-animation-manual-id inputmode="numeric" autocomplete="off" value="${safe(manualConfirmAsset)}"></label>`+
        `<label><input type="checkbox" data-animation-manual-checked ${manualConfirmChecked?'checked':''}> I confirm that I replaced this exact animation in Roblox Studio under the ID above.</label>`+
        `<small>This records USER_ATTESTED, not Roblox Approved. The old ID and full publication history are retained.</small></div>`:'')+
      `<div id="animation-replace-result" class="animation-review-result" aria-live="polite">${row.status==='CHANGED'?'Waiting for Studio replacement or explicit confirmation.':row.user_attested?'Previously marked as user-attested; not verified by Roblox.':'Current source publication registered.'}</div>`;
    $('animation-replace-confirm').disabled=!replacementPath||busy;
    $('animation-replace-check').disabled=busy||row.status!=='CHANGED';
    const manualId=el.querySelector('[data-animation-manual-id]');if(manualId)manualId.oninput=()=>{manualConfirmAsset=manualId.value.trim();syncManualConfirm();};
    const confirm=el.querySelector('[data-animation-manual-checked]');if(confirm)confirm.onchange=()=>{manualConfirmChecked=confirm.checked;syncManualConfirm();};
    syncManualConfirm();
  }
  function openReplacement(row){replacing=row;replacementPath='';manualConfirmAsset='';manualConfirmChecked=false;renderReplacement();open('animation-replace-dialog')}
  async function chooseReplacement(){try{const result=await api.request('/api/files/choose-character-animation-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialPath:api.state().animationFolder})});if(result.path){replacementPath=result.path;renderReplacement()}}catch(e){api.toast(e.message,true)}}
  async function stageReplacement(){if(!replacing||!replacementPath||busy)return;busy=true;const before=replacing.asset_id;try{const result=await api.request('/api/animations/'+encodeURIComponent(replacing.clip_id)+'/stage-replacement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sourcePath:replacementPath})});if(result.assetId!==before)throw Error('Asset ID changed unexpectedly');await api.load();replacing=(api.state().animations?.items||[]).find(r=>r.clip_id===replacing.clip_id)||replacing;renderReplacement();$('animation-replace-result').textContent=result.status==='CHANGED'?'Файл подготовлен. Выполни ручной реимпорт в Studio и затем проверь Roblox.':'Файл не изменился; реимпорт не требуется.'}catch(e){api.toast(e.message,true)}finally{busy=false;$('animation-replace-confirm').disabled=!replacementPath;$('animation-replace-check').disabled=replacing?.status!=='CHANGED'}}
  async function confirmReplacementManually(){
    if(!replacing||busy||replacing.status!=='CHANGED'||!manualConfirmChecked||manualConfirmAsset!==String(replacing.asset_id))return;
    const row=replacing;
    if(!confirm(`Confirm that ${row.name} was REPLACED in Roblox Studio under ID ${row.asset_id}? This is your declaration, not Roblox verification.`))return;
    busy=true;syncManualConfirm();
    try{
      const result=await api.request('/api/animations/'+encodeURIComponent(row.clip_id)+'/confirm-studio-replacement',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({assetId:row.asset_id,sha256:row.sha256,attested:true})});
      await api.load();
      replacing=(api.state().animations?.items||[]).find(r=>r.clip_id===row.clip_id)||row;
      renderReplacement();
      $('animation-replace-result').textContent='Marked USER_ATTESTED (not Cloud verified). Asset ID preserved. Prepare Studio Sync and connect Rojo before Play.';
      api.toast('User attestation recorded · not Roblox-verified');
    }catch(e){api.toast(e.message,true)}finally{busy=false;syncManualConfirm();}
  }
  async function prepareStudioSync(){
    const status=$('animation-studio-sync-status');
    status.textContent='Regenerating canonical Animation Registry for Rojo…';
    try{const result=await api.request('/api/animations/prepare-studio-sync',{method:'POST'});
      status.textContent=`Exported ${result.publishedClips}/${result.clips} animations (${result.changedClips} changed). Studio is NOT synced by this button. Connect / Sync Rojo and restart Play.`;
      api.toast('Animation Registry exported. Sync Rojo to Studio; then restart Play.');
    }catch(e){status.textContent='Animation export failed: '+e.message;api.toast(e.message,true);}
  }
  async function checkReplacement(){if(!replacing||busy)return;busy=true;try{const result=await api.request('/api/animations/'+encodeURIComponent(replacing.clip_id)+'/check-replacement',{method:'POST'});await api.load();replacing=(api.state().animations?.items||[]).find(r=>r.clip_id===replacing.clip_id)||replacing;renderReplacement();$('animation-replace-result').textContent=result.confirmed?'Done! Roblox подтвердил новую Approved-версию; Asset ID сохранён.':result.pending?'Ожидание: новой одобренной версии Roblox пока нет.':'Проверка: '+(result.details?.[0]?.message||'нет ожидающей замены.')}catch(e){api.toast(e.message,true)}finally{busy=false;$('animation-replace-confirm').disabled=!replacementPath;$('animation-replace-check').disabled=replacing?.status!=='CHANGED'}}
  function init(callbacks){api=callbacks;
    document.querySelectorAll('[data-animation-gender]').forEach(button=>button.addEventListener('click',()=>{
      const selected=(api.state().animations?.characters||[]).find(row=>row.gender===button.dataset.animationGender);
      if(!selected){api.toast('Сначала зарегистрируй персонажа этого пола',true);return;}
      api.state().animationCharacter=selected.id;
      api.state().animationSelected=null;
      api.load();
    }));
    $('animation-common-search').addEventListener('input',event=>{
      commonQuery=event.target.value.trim().toLocaleLowerCase();renderCommonPicker();
    });
    $('animation-common-select').addEventListener('change',event=>{
      commonSelection=event.target.value;renderCommonPicker();
    });
    $('animation-common-assign').addEventListener('click',()=>{
      if(commonSelection)setCommon(commonSelection,true);
    });
    const search=$('animation-name-search');
    search.addEventListener('input',()=>{nameQuery=search.value.trim().toLocaleLowerCase();renderRows()});
    search.addEventListener('keydown',e=>{if(e.key==='Escape'){search.value='';nameQuery='';renderRows();}});
    $('animation-show-missing').checked=showMissing;$('animation-show-missing').addEventListener('change',e=>{showMissing=e.target.checked;try{localStorage.setItem(missingKey,showMissing?'1':'0')}catch{}api.render()});
    document.querySelectorAll('[data-animation-sort]').forEach(th=>{const action=()=>{const key=th.dataset.animationSort;sortDir=sortKey===key?-sortDir:1;sortKey=key;api.render()};th.addEventListener('click',action);th.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();action()}})});
    document.querySelectorAll('[data-animation-close]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));$('animation-register-selected').onclick=registerSelected;$('animation-scan-review').addEventListener('change',syncScanPublishButton);$('animation-replace-choose').onclick=chooseReplacement;$('animation-replace-confirm').onclick=stageReplacement;$('animation-replace-check').onclick=checkReplacement;$('animation-replace-manual').onclick=confirmReplacementManually;$('animation-prepare-sync').onclick=prepareStudioSync;
  }
  window.game1AnimationUI={init,renderRows,renderRules,scanFolder,refreshAttackTimelines};
})();
