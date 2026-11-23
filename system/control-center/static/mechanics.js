/* Compact mechanics tech cards + isolated, validated heat-source tuning. */
(() => {
  'use strict';
  const root = document.getElementById('mechanics-view');
  if (!root) return;
  const get = id => document.getElementById(id);
  const state = {catalog: null, domain: 'house', query: '', open: null, mode: new Map(), sources: new Map(), errors: new Map(), fireplaceSettings: null, fireplaceLimits: null, fireplaceBusy: false};
  const DOMAIN_KEY = 'game1.mechanics.domain.v1';
  try {state.domain = localStorage.getItem(DOMAIN_KEY) || 'house';} catch {}

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
  function currentDomain() {
    return state.catalog?.domains?.find(domain => domain.id === state.domain) || null;
  }
  function status(message, error = false) {
    const node = get('mechanics-status');
    node.textContent = message;
    node.classList.toggle('mx-error', error);
    node.hidden = !message;
  }
  function setDomain(id) {
    if (!state.catalog?.domains.some(d => d.id === id)) return;
    state.domain = id;
    state.open = null;
    state.query = '';
    get('mechanics-search').value = '';
    try {localStorage.setItem(DOMAIN_KEY, id);} catch {}
    render();
  }
  function renderTabs() {
    const host = get('mechanics-domains');
    host.replaceChildren();
    for (const domain of state.catalog.domains) {
      const button = element('button', 'mx-domain', domain.label);
      button.type = 'button';
      button.role = 'tab';
      button.id = `mx-tab-${domain.id}`;
      button.setAttribute('aria-selected', domain.id === state.domain ? 'true' : 'false');
      button.setAttribute('aria-controls', 'mechanics-list');
      const count = element('span', 'mx-tab-count', domain.items.length);
      button.append(count);
      button.addEventListener('click', () => setDomain(domain.id));
      host.append(button);
    }
  }
  function makeButton(text, active, callback) {
    const button = element('button', 'mx-switch'+(active?' active':''), text);
    button.type = 'button';
    button.setAttribute('aria-pressed', String(active));
    button.addEventListener('click', callback);
    return button;
  }
  function selectMode(item, body, mode) {
    state.mode.set(item.id, mode);
    renderBody(item, body);
  }
  const TUNING_LABELS = {
    FuelDurationSeconds: ['Дрова · сек', 'House'],
    EmbersDurationSeconds: ['Угли · сек', 'House'],
    CampfireDurationSeconds: ['Костёр · сек', 'Campfire'],
    CookingSecondsOnFire: ['Готовка на огне · сек', 'Cooking'],
    CookingSecondsOnEmbers: ['Готовка на углях · сек', 'Cooking'],
    ProgressVisibleRadius: ['Индикаторы · studs', 'UI'],
  };
  async function loadSettings(item, body) {
    if (state.fireplaceSettings || state.fireplaceBusy) return;
    state.fireplaceBusy = true;
    try {
      const response = await fetch('/api/mechanics/fireplace-settings');
      const data = await response.json();
      if (!response.ok || !data.settings) throw new Error(data.error || `HTTP ${response.status}`);
      state.fireplaceSettings = data.settings;
      state.fireplaceLimits = data.limits;
      if (body.isConnected) renderBody(item, body);
    } catch (error) {status(`Настройки: ${error.message}`, true);}
    finally {state.fireplaceBusy = false;}
  }
  function renderSettings(item, body, host) {
    if (!state.fireplaceSettings) {
      host.append(element('p','mx-footnote','Загрузка параметров…'));
      void loadSettings(item, body);
      return;
    }
    const form = element('form', 'mx-settings');
    const grid = element('div', 'mx-setting-grid');
    const entries = Object.entries(state.fireplaceSettings);
    for (const [key, value] of entries) {
      if (!TUNING_LABELS[key]) continue;
      const [title, group] = TUNING_LABELS[key];
      const field = element('label', 'mx-setting');
      const name = element('span', 'mx-setting-name', title);
      const input = element('input');
      const limits = state.fireplaceLimits?.[key] || [1, 7200];
      input.type = 'number';
      input.step = '1';
      input.min = String(limits[0]);
      input.max = String(limits[1]);
      input.value = String(value);
      input.required = true;
      input.name = key;
      input.setAttribute('aria-label', title);
      field.append(name, input, element('small','mx-setting-group',group));
      grid.append(field);
    }
    form.append(grid);
    const actions = element('div','mx-settings-actions');
    const save = element('button','primary','Сохранить настройки');
    save.type = 'submit';
    actions.append(save);
    actions.append(element('p','mx-footnote','После сохранения обнови Studio Sync и перезапусти Play. Fire Tuner на существующих кострах сохраняет свои настройки. Дистанции USE/AIM сокетов настраиваются в Options → Sockets.'));
    form.append(actions);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (state.fireplaceBusy || !form.reportValidity()) return;
      const values = Object.fromEntries(entries.map(([key,value]) => [key,form.elements.namedItem(key) ? Number(form.elements.namedItem(key).value) : value]));
      save.disabled = true;
      state.fireplaceBusy = true;
      try {
        const response = await fetch('/api/mechanics/fireplace-settings',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({settings:values,expected:state.fireplaceSettings}),
        });
        const data = await response.json();
        if (!response.ok || !data.settings) throw new Error(data.error || `HTTP ${response.status}`);
        state.fireplaceSettings = data.settings;
        state.sources.delete(`${item.id}:fireplace-config`);
        status('Настройки сохранены · требуется Studio Sync и перезапуск Play.');
        if (body.isConnected) renderBody(item, body);
      } catch (error) {status(`Настройки: ${error.message}`,true);}
      finally {state.fireplaceBusy = false;save.disabled = false;}
    });
    host.append(form);
  }
  function renderBody(item, body) {
    const mode = state.mode.get(item.id) || 'brief';
    body.replaceChildren();
    const switcher = element('div', 'mx-switcher');
    for (const [key, label] of [['brief','Кратко'], ['full','Полная карта'], ['scripts','Скрипты'], ...(item.id === 'fireplace' ? [['settings','Настройки']] : [])]) {
      switcher.append(makeButton(label, mode === key, () => selectMode(item, body, key)));
    }
    body.append(switcher);
    const content = element('div', 'mx-card-content');
    if (mode === 'brief') {
      content.append(element('p', 'mx-lead', item.summary));
      if (item.sockets?.length) {
        const label = element('div', 'mx-label', 'Сокеты / опоры');
        const tokens = element('div', 'mx-tokens');
        for (const socket of item.sockets) tokens.append(element('code', 'mx-token', socket));
        content.append(label, tokens);
      }
    } else if (mode === 'full') {
      content.append(element('p', 'mx-lead', item.summary));
      const sections = item.sections || [];
      for (const section of sections) {
        const sectionNode = element('section', 'mx-doc-section');
        sectionNode.append(element('h4', '', section.title));
        const list = element('ol', 'mx-steps');
        for (const line of section.lines) list.append(element('li', '', line));
        sectionNode.append(list);
        content.append(sectionNode);
      }
      const references = element('p', 'mx-footnote', 'Источники: действующие Luau-модули и техническая документация проекта. Полный текст доступен во вкладке «Скрипты».');
      content.append(references);
    } else if (mode === 'settings' && item.id === 'fireplace') {
      renderSettings(item, body, content);
    } else {
      content.append(element('p', 'mx-footnote', 'Исходный текст файлов проекта · только чтение. Содержимое загружается по запросу.'));
      const sourceList = element('div', 'mx-source-list');
      for (const source of item.sources || []) {
        const panel = element('details', 'mx-source');
        const summary = element('summary', 'mx-source-heading');
        summary.append(element('strong', '', source.title), element('code', '', source.path));
        const viewer = element('div', 'mx-source-viewer');
        viewer.append(element('p', 'mx-footnote', 'Открой файл, чтобы прочитать актуальную версию.'));
        panel.append(summary, viewer);
        panel.addEventListener('toggle', () => {
          if (panel.open) void loadSource(item.id, source, viewer);
        });
        sourceList.append(panel);
      }
      content.append(sourceList);
    }
    body.append(content);
  }
  async function loadSource(itemId, source, viewer) {
    const key = `${itemId}:${source.id}`;
    const present = state.sources.get(key);
    if (present !== undefined) {
      showSource(viewer, present);
      return;
    }
    if (viewer.dataset.loading === 'true') return;
    viewer.dataset.loading = 'true';
    viewer.replaceChildren(element('p','mx-footnote','Загрузка файла…'));
    try {
      const response = await fetch(`/api/mechanics/source?item=${encodeURIComponent(itemId)}&source=${encodeURIComponent(source.id)}`);
      const data = await response.json();
      if (!response.ok || typeof data.content !== 'string') throw new Error(data.error || `HTTP ${response.status}`);
      state.sources.set(key, data.content);
      if (viewer.isConnected) showSource(viewer, data.content);
    } catch (error) {
      if (viewer.isConnected) viewer.replaceChildren(element('p', 'mx-error', `Не удалось открыть файл: ${error.message}`));
    } finally {viewer.dataset.loading = 'false';}
  }
  function showSource(viewer, content) {
    const code = element('code', '', content);
    const pre = element('pre', 'mx-code');
    pre.append(code);
    viewer.replaceChildren(pre);
  }
  function addCard(item, host) {
    const details = element('details', 'mx-card');
    details.dataset.id = item.id;
    const summary = element('summary', 'mx-card-head');
    summary.append(element('span', 'mx-chevron', '›'));
    const label = element('span', 'mx-card-title', item.title);
    const brief = element('span', 'mx-card-subtitle', item.summary);
    const name = element('span', 'mx-card-name');
    name.append(label, brief);
    summary.append(name, element('span','mx-kind',item.kind));
    const body = element('div', 'mx-card-body');
    details.append(summary, body);
    details.open = state.open === item.id;
    if (details.open) renderBody(item, body);
    details.addEventListener('toggle', () => {
      if (!details.isConnected) return;
      if (details.open) {
        state.open = item.id;
        if (!body.children.length) renderBody(item, body);
        for (const other of host.querySelectorAll('.mx-card[open]')) if (other !== details) other.open = false;
      } else if (state.open === item.id) state.open = null;
    });
    host.append(details);
  }
  function render() {
    const domain = currentDomain();
    if (!domain) return;
    renderTabs();
    get('mechanics-domain-title').textContent = domain.label;
    get('mechanics-domain-description').textContent = domain.description;
    const query = state.query.trim().toLocaleLowerCase('ru');
    const filtered = domain.items.filter(item =>
      [item.title,item.summary,item.kind,...(item.sockets||[])].join(' ').toLocaleLowerCase('ru').includes(query));
    get('mechanics-result-count').textContent = `${filtered.length} / ${domain.items.length}`;
    const host = get('mechanics-list');
    host.replaceChildren();
    if (!filtered.length) {
      host.append(element('div','mx-empty',domain.items.length
        ? 'По запросу ничего не найдено.'
        : 'Карты этого раздела пока не опубликованы. Для NPC и Monster предусмотрены индивидуальные карточки и ссылки на скрипты каждого вида.'));
      return;
    }
    for (const item of filtered) addCard(item, host);
  }
  let loading = null;
  async function load() {
    if (state.catalog) return;
    if (loading) return loading;
    status('Загрузка технических карт…');
    loading = (async () => {
      try {
        const response = await fetch('/api/mechanics');
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.domains)) throw new Error(data.error || `HTTP ${response.status}`);
        state.catalog = data;
        if (!currentDomain()) state.domain = 'house';
        render();
        status('');
      } catch (error) {status(`Не удалось загрузить Mechanics: ${error.message}`, true);}
      finally {loading = null;}
    })();
    return loading;
  }
  get('mechanics-refresh').addEventListener('click', () => {
    state.catalog = null;
    state.sources.clear();
    state.open = null;
    get('mechanics-list').replaceChildren();
    void load();
  });
  get('mechanics-search').addEventListener('input', event => {
    state.query = event.target.value;
    render();
  });
  window.game1MechanicsLoad = load;
})();
