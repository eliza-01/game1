/* Shared, domain-scoped Collision Blueprint UI: Location Assets + Real Estate. */
(() => {
  const get = id => document.getElementById(id);
  const escapeHTML = str => String(str ?? '').replace(/[&<>"']/g,
    ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const formatDiff = diff => !diff ? '' : ['added','removed','modified'].map(key =>
    `${key}: ${(diff[key] || []).length}${diff[key]?.length ? ' ('+diff[key].join(', ')+')' : ''}`).join(' · ');
  function attach(prefix, kind, emptyText) {
    if (!get(`${prefix}-panel`)) return null;
    const state = {slug:'', revision:0, count:0, busy:false, requestId:0};
    const label = () => get(`${prefix}-asset`);
    const endpoint = slug => `/api/${kind}/${encodeURIComponent(slug)}`;
    const status = message => { get(`${prefix}-status`).textContent=message; };
    const buttons = () => {
      for (const phase of ['validate','capture','preview','clear']) {
        get(`${prefix}-${phase}`).disabled = state.busy || !state.slug ||
          (phase==='preview' && state.revision===0);
      }
      label().disabled = state.busy;
    };
    async function load(slug) {
      state.slug=slug;
      state.revision=0;
      const active=++state.requestId;
      if (!slug) {
        state.count=0;
        get(`${prefix}-meta`).textContent='Blueprint: не выбран';
        get(`${prefix}-history`).textContent='Выбери ассет.';
        status(emptyText);
        buttons(); return;
      }
      buttons();
      try {
        const [current,history] = await Promise.all([
          request(`${endpoint(slug)}/collision-blueprint`),
          request(`${endpoint(slug)}/collision-history?limit=25`),
        ]);
        if (active!==state.requestId) return;
        state.revision=Number(current.revision||0);
        state.count=current.blueprint?.parts?.length||0;
        get(`${prefix}-meta`).textContent=`${slug} · revision ${state.revision} · ${state.count} Parts`;
        const entries=history.history||[];
        get(`${prefix}-history`).innerHTML=entries.length
          ? entries.map(item=>`<div>r${Number(item.revision)} · ${Number(item.partCount)} Parts · ${escapeHTML(new Date(item.capturedAt*1000).toLocaleString())} · ${escapeHTML(String(item.sha256).slice(0,12))}</div>`).join('')
          : 'Пока нет сохранённых ревизий.';
        status(state.revision ? 'Можно проверить сохранённый Blueprint или снять новый Capture.' :
          'Выдели опубликованную модель вместе с оригинальными Parts в Studio → Validate → Capture.');
      } catch(error) {
        if(active===state.requestId)status(`Ошибка загрузки Blueprint: ${error.message}`);
      } finally {buttons();}
    }
    async function operate(phase) {
      if (!state.slug||state.busy)return;
      const slug=state.slug;
      const names={validate:'Validate',capture:'Capture',preview:'Preview','clear-preview':'Clear Preview'};
      state.busy=true; buttons();
      status(`${names[phase]} · обращение к Roblox Studio…`);
      try {
        const data=await request(`${endpoint(slug)}/collision-studio`, {
          method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phase})});
        const result=data.studio;
        const note=`${names[phase]} ✓ · ${Number(result.partCount)} Parts · ${formatDiff(result.diff)}`;
        if (phase==='capture') {
          await load(slug);
          status(`${note}\nRevision: ${result.revision} · ${result.changed?'сохранена новая ревизия':'нет изменений'}.`+
            (kind==='real-estate'?' Теперь выполни Sync entire house.':''));
        } else status(note);
      } catch(error) {status(`${names[phase]} failed: ${error.message}`);}
      finally {state.busy=false;buttons();}
    }
    label().addEventListener('change',()=>load(label().value));
    get(`${prefix}-validate`).onclick=()=>operate('validate');
    get(`${prefix}-capture`).onclick=()=>operate('capture');
    get(`${prefix}-preview`).onclick=()=>operate('preview');
    get(`${prefix}-clear`).onclick=()=>operate('clear-preview');
    buttons();
    return {
      select(slug, scroll=true) {
        const target=String(slug||'');
        if (target && ![...label().options].some(option=>option.value===target)) return;
        if (state.slug!==target) {
          label().value=target;
          load(target);
        }
        if (scroll) get(`${prefix}-panel`).scrollIntoView({behavior:'smooth',block:'center'});
      },
      refresh(assets) {
        const options=(assets||[]).slice().sort((a,b)=>String(a.name_en||a.slug).localeCompare(String(b.name_en||b.slug)));
        const old=state.slug;
        label().replaceChildren(new Option('Выбери ассет',''),...options.map(item=>
          new Option(`${item.name_en||item.slug} · ${item.slug}`,item.slug)));
        if (old && options.some(item=>item.slug===old)) {
          label().value=old;
          if (!state.busy)load(old);
        } else if (old)load('');
        buttons();
      },
    };
  }
  const location=attach('location-collision','location-assets','Выбери зарегистрированный Location Asset.');
  if(location) {
    window.game1LocationCollisionSelect=location.select;
    window.game1LocationCollisionRefresh=location.refresh;
  }
  const house=attach('house-collision','real-estate','Выбери зарегистрированный дом.');
  if(house) {
    window.game1RealEstateCollisionSelect=house.select;
    window.game1RealEstateCollisionRefresh=house.refresh;
  }
})();
