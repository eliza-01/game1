/* M339 · Development Kanban. No Roblox runtime or browser-local canonical state. */
(() => {
  const $kb = id => document.getElementById(id);
  const statuses = ['PROPOSED','READY','IN_PROGRESS','CODE_COMPLETE','VALIDATING','DONE','BLOCKED','ON_HOLD'];
  const testStates = ['NOT_RUN','PASS','FAIL','BLOCKED'];
  const model = {cards:[], open:null, detail:null, busy:false};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const encode = id => encodeURIComponent(id);
  function notice(value, error=false) { const el=$kb('kb-notice'); if(el){el.textContent=value;el.classList.toggle('kb-error',error)} }
  async function api(path, options) {
    const res=await fetch('/api/kanban'+path,options);
    let data={};try{data=await res.json()}catch{}
    if(!res.ok)throw new Error(data.error||`HTTP ${res.status}`);
    return data;
  }
  function metric() {
    const total=model.cards.length;
    const tasks=model.cards.flatMap(c=>c.tasks||[]);
    $kb('kb-metrics').innerHTML=`<span><strong>${total}</strong>механик</span><span><strong>${model.cards.filter(c=>c.status==='IN_PROGRESS').length}</strong>в работе</span><span><strong>${model.cards.filter(c=>c.status==='DONE').length}</strong>проверено</span><span><strong>${tasks.filter(x=>x.done).length}/${tasks.length}</strong>пунктов</span>`;
  }
  function cards() {
    metric();const host=$kb('kb-cards');host.replaceChildren();
    const query=$kb('kb-search').value.toLowerCase().trim(),filter=$kb('kb-status').value;
    for(const c of model.cards){
      if(filter&&c.status!==filter)continue;
      if(query&&!`${c.id} ${c.title} ${c.domain} ${c.owner} ${(c.tasks||[]).map(t=>t.title).join(' ')}`.toLowerCase().includes(query))continue;
      const el=document.createElement('details');el.className='kb-card';el.dataset.id=c.id;el.open=model.open===c.id;
      const count=c.tasks.filter(t=>t.done).length;
      el.innerHTML=`<summary><div class="kb-head"><span class="kb-title">${escape(c.title)}</span><span class="kb-sub">${escape(c.id)} · ${escape(c.domain)} · ${escape(c.status)} · ${escape(c.priority)} · ${escape(c.owner)} · r${c.revision}</span></div><span class="kb-progress">${count}/${c.tasks.length} ▾</span></summary><div class="kb-body"></div>`;
      el.addEventListener('toggle',()=>{if(el.open){model.open=c.id;for(const sibling of host.children)if(sibling!==el)sibling.open=false;loadDetail(c.id)}else if(model.open===c.id){model.open=null;model.detail=null}});
      host.append(el);
      if(el.open&&model.detail?.card.id===c.id)renderDetail(el.querySelector('.kb-body'),model.detail);
    }
    if(!host.children.length)host.textContent='Нет карточек по выбранному фильтру.';
  }
  async function load() {
    try{const result=await api('');model.cards=result.cards;notice('Данные хранятся в docs/kanban · все пункты изначально PROPOSED');cards()}
    catch(error){notice(error.message,true)}
  }
  async function loadDetail(id){
    try{const data=await api('/'+encode(id));if(model.open!==id)return;model.detail=data;const el=Array.from($kb('kb-cards').children).find(e=>e.dataset.id===id);if(el)renderDetail(el.querySelector('.kb-body'),data)}
    catch(error){notice(error.message,true)}
  }
  async function mutate(id,payload){
    if(model.busy)return;
    const current=model.detail;
    if(!current||current.card.id!==id)return;
    model.busy=true;
    try{
      const data=await api('/'+encode(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expectedRevision:current.card.revision,...payload})});
      model.detail=data;
      model.cards=model.cards.map(c=>c.id===id?data.card:c);
      notice(`${id} сохранена · revision ${data.card.revision}`);
      cards();
    }catch(error){notice(error.message,true);await loadDetail(id)}
    finally{model.busy=false}
  }
  function optionSet(values,current){return values.map(value=>`<option value="${value}" ${value===current?'selected':''}>${value}</option>`).join('')}
  function renderDetail(body,data){
    if(!body)return;
    const c=data.card,id=c.id;
    body.replaceChildren();
    const main=document.createElement('div');main.className='kb-actions';
    main.innerHTML=`<label>Статус<select class="kb-status-control">${optionSet(statuses,c.status)}</select></label><span class="kb-notice">При DONE все пункты и проверки должны быть подтверждены.</span>`;
    main.querySelector('select').addEventListener('change',e=>mutate(id,{action:'status',status:e.target.value}));body.append(main);
    if(c.dependsOn?.length){const depends=document.createElement('p');depends.className='kb-notice';depends.textContent='Зависимости: '+c.dependsOn.map(dep=>{const record=model.cards.find(x=>x.id===dep);return dep+' ('+(record?.status||'нет данных')+')'}).join(', ');body.append(depends)}
    const taskGroup=document.createElement('section');taskGroup.className='kb-group';taskGroup.innerHTML='<h4>Обязательные шаги</h4>';
    c.tasks.forEach(task=>{
      const label=document.createElement('label');label.className='kb-item';
      const check=document.createElement('input');check.type='checkbox';check.checked=task.done;
      check.addEventListener('change',()=>mutate(id,{action:'task',itemId:task.id,done:check.checked}));
      const text=document.createElement('span');text.textContent=task.title;label.append(check,text);taskGroup.append(label);
    });
    const addTask=document.createElement('div');addTask.className='kb-add-row';
    const taskText=document.createElement('input');taskText.maxLength=300;taskText.placeholder='Добавить обязательный шаг';
    const addTaskButton=document.createElement('button');addTaskButton.type='button';addTaskButton.textContent='+ Шаг';
    addTaskButton.onclick=()=>mutate(id,{action:'task-add',title:taskText.value});addTask.append(taskText,addTaskButton);taskGroup.append(addTask);body.append(taskGroup);
    const testGroup=document.createElement('section');testGroup.className='kb-group';testGroup.innerHTML='<h4>Проверки · PASS требует доказательства</h4>';
    c.acceptance.forEach(test=>{
      const row=document.createElement('div');row.className='kb-test';
      const name=document.createElement('span');name.textContent=test.title;
      const status=document.createElement('select');status.innerHTML=optionSet(testStates,test.status);
      const evidence=document.createElement('input');evidence.type='text';evidence.maxLength=2000;evidence.placeholder='Лог, коммит или результат ручной проверки';evidence.value=test.evidence||'';
      const save=document.createElement('button');save.type='button';save.textContent='Сохранить проверку';
      save.onclick=()=>mutate(id,{action:'acceptance',itemId:test.id,status:status.value,evidence:evidence.value});
      row.append(name,status,evidence,save);testGroup.append(row);
    });
    const addTest=document.createElement('div');addTest.className='kb-add-row';
    const testText=document.createElement('input');testText.maxLength=300;testText.placeholder='Добавить критерий приёмки';
    const addTestButton=document.createElement('button');addTestButton.type='button';addTestButton.textContent='+ Проверка';
    addTestButton.onclick=()=>mutate(id,{action:'acceptance-add',title:testText.value});addTest.append(testText,addTestButton);testGroup.append(addTest);body.append(testGroup);
    const doc=document.createElement('section');doc.className='kb-group kb-doc';doc.innerHTML='<h4>Документация механики · единственный канонический файл</h4>';
    const path=document.createElement('small');path.className='kb-notice';path.textContent=c.specPath;doc.append(path);
    const pre=document.createElement('pre');pre.textContent=data.spec;doc.append(pre);
    const edit=document.createElement('textarea');edit.value=data.spec;edit.hidden=true;doc.append(edit);
    const reason=document.createElement('input');reason.type='text';reason.maxLength=1000;reason.placeholder='Причина изменения (не менее 8 символов)';reason.hidden=true;doc.append(reason);
    const approval=document.createElement('label');approval.className='kb-item';approval.hidden=true;
    const confirm=document.createElement('input');confirm.type='checkbox';const text=document.createElement('span');text.textContent='Подтверждаю изменение утверждённого технического контракта';approval.append(confirm,text);doc.append(approval);
    const buttons=document.createElement('div');buttons.className='kb-doc-controls';
    const toggle=document.createElement('button');toggle.type='button';toggle.textContent='Редактировать документацию';
    const save=document.createElement('button');save.type='button';save.className='primary';save.textContent='Сохранить версию';save.hidden=true;
    const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Отмена';cancel.hidden=true;
    function editing(value){pre.hidden=value;edit.hidden=!value;reason.hidden=!value;approval.hidden=!value;save.hidden=!value;cancel.hidden=!value;toggle.hidden=value}
    toggle.onclick=()=>editing(true);cancel.onclick=()=>editing(false);
    save.onclick=()=>mutate(id,{action:'spec',spec:edit.value,reason:reason.value,confirmPolicyChange:confirm.checked});
    buttons.append(toggle,save,cancel);doc.append(buttons);body.append(doc);
    const history=document.createElement('section');history.className='kb-group';
    history.innerHTML='<h4>История изменений</h4>';
    const loadHistory=document.createElement('button');loadHistory.type='button';loadHistory.textContent='Показать историю';
    const events=document.createElement('div');events.className='kb-history';
    loadHistory.onclick=async()=>{try{const data=await api('/'+encode(id)+'/history');events.replaceChildren();if(!data.events.length)events.textContent='Изменений ещё нет';data.events.forEach(event=>{const row=document.createElement('div');row.textContent=`r${event.revision} · ${event.time} · ${event.detail}`;events.append(row)})}catch(error){notice(error.message,true)}};
    history.append(loadHistory,events);body.append(history);
  }
  const filter=$kb('kb-status');for(const value of statuses){const o=document.createElement('option');o.value=value;o.textContent=value;filter.append(o)}
  $kb('kb-search').addEventListener('input',cards);filter.addEventListener('change',cards);
  $kb('kb-refresh').addEventListener('click',load);
  const createForm=$kb('kb-create-form');
  $kb('kb-create-toggle').onclick=()=>{createForm.hidden=!createForm.hidden};
  $kb('kb-create-cancel').onclick=()=>{createForm.hidden=true};
  createForm.addEventListener('submit',async event=>{
    event.preventDefault();
    if(model.busy)return;
    const formData=new FormData(createForm);
    model.busy=true;
    try{
      const result=await api('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(formData.entries()))});
      createForm.reset();createForm.hidden=true;model.open=result.card.id;model.detail=result;
      await load();notice(`Создана ${result.card.id}`);
    }catch(error){notice(error.message,true)}finally{model.busy=false}
  });
  $kb('kb-export').addEventListener('click',async()=>{
    try{const data=await api('/export');const blob=new Blob([data.markdown],{type:'text/markdown;charset=utf-8'});
      const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Eyesland_Kanban_Status.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(error){notice(error.message,true)}
  });
  window.game1KanbanLoad=load;
})();
