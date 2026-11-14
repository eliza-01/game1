/* M343B: separate Studio authoring workflow. No Place/Sync/Model publication writes. */
(() => {
  const get = id => document.getElementById(id);
  const state = {slug: '', revision: 0, count: 0, busy: false, requestId: 0};
  const escapeHTML = str => String(str ?? '').replace(/[&<>"']/g,
    ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const label = () => get('location-collision-asset');
  const status = text => {get('location-collision-status').textContent = text;};
  const formatDiff = diff => {
    if (!diff) return '';
    const sections = ['added','removed','modified'].map(key =>
      `${key}: ${(diff[key] || []).length}${diff[key]?.length ? ' ('+diff[key].join(', ')+')' : ''}`);
    return sections.join(' · ');
  };
  const buttons = () => {
    for (const phase of ['validate','capture','preview','clear']) {
      const button = get('location-collision-' + phase);
      button.disabled = state.busy || !state.slug || (phase === 'preview' && state.revision === 0);
    }
    label().disabled = state.busy;
  };
  async function load(slug) {
    if (!slug) {
      state.slug = ''; state.revision = 0; state.count = 0;
      get('location-collision-meta').textContent = 'Blueprint: не выбран';
      get('location-collision-history').textContent = 'Выбери ассет.';
      status('Выбери зарегистрированный Location Asset.');
      buttons(); return;
    }
    state.slug = slug;
    state.revision = 0;
    buttons();
    const active = ++state.requestId;
    try {
      const [current, history] = await Promise.all([
        request(`/api/location-assets/${encodeURIComponent(slug)}/collision-blueprint`),
        request(`/api/location-assets/${encodeURIComponent(slug)}/collision-history?limit=25`),
      ]);
      if (active !== state.requestId) return;
      state.revision = Number(current.revision || 0);
      state.count = current.blueprint?.parts?.length || 0;
      get('location-collision-meta').textContent =
        `${slug} · revision ${state.revision} · ${state.count} Parts`;
      const entries = history.history || [];
      get('location-collision-history').innerHTML = entries.length
        ? entries.map(entry => `<div>r${Number(entry.revision)} · ${Number(entry.partCount)} Parts · ${escapeHTML(new Date(entry.capturedAt * 1000).toLocaleString())} · ${escapeHTML(String(entry.sha256).slice(0,12))}</div>`).join('')
        : 'Пока нет сохранённых ревизий.';
      status(state.revision ? 'Можно показать сохранённый Blueprint или сделать новый Capture.' :
        'Blueprint пока не создан. Выдели модель ассета вместе с любыми Parts в Studio → Validate → Capture.');
    } catch (error) {
      if (active === state.requestId) status(`Ошибка загрузки Blueprint: ${error.message}`);
    } finally { buttons(); }
  }
  async function operate(phase) {
    if (!state.slug || state.busy) return;
    const slug = state.slug;
    state.busy = true;
    buttons();
    const names = {'validate':'Validate', 'capture':'Capture', 'preview':'Preview', 'clear-preview':'Clear Preview'};
    status(`${names[phase]} · обращение к Roblox Studio…`);
    try {
      const data = await request(`/api/location-assets/${encodeURIComponent(slug)}/collision-studio`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phase})});
      const result = data.studio;
      const note = `${names[phase]} ✓ · ${Number(result.partCount)} Parts · ${formatDiff(result.diff)}`;
      if (phase === 'capture') {
        await load(slug);
        status(`${note}\nRevision: ${result.revision} · ${result.changed ? 'сохранена новая ревизия' : 'нет изменений'}.`);
      } else {
        status(note);
      }
    } catch (error) {
      status(`${names[phase]} failed: ${error.message}`);
    } finally { state.busy = false; buttons(); }
  }
  label().addEventListener('change', () => load(label().value));
  get('location-collision-validate').onclick = () => operate('validate');
  get('location-collision-capture').onclick = () => operate('capture');
  get('location-collision-preview').onclick = () => operate('preview');
  get('location-collision-clear').onclick = () => operate('clear-preview');
  window.game1LocationCollisionSelect = slug => {
    if (![...label().options].some(option => option.value === slug)) return;
    label().value = slug;
    load(slug);
    get('location-collision-panel').scrollIntoView({behavior:'smooth', block:'center'});
  };
  window.game1LocationCollisionRefresh = assets => {
    const options = (assets || []).slice().sort((a,b) =>
      String(a.name_en || a.slug).localeCompare(String(b.name_en || b.slug)));
    const old = state.slug;
    label().replaceChildren(new Option('Выбери ассет', ''),
      ...options.map(item => new Option(`${item.name_en || item.slug} · ${item.slug}`, item.slug)));
    if (old && options.some(asset => asset.slug === old)) {
      label().value = old;
      if (!state.busy) load(old);
    } else if (old) load('');
    buttons();
  };
  buttons();
})();
