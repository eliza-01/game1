/* Central Atlas Registry view. Retirement and dependency checking live on server. */
(() => {
  const state = {families: [], active: null, busy: false};
  const node = id => document.getElementById(id);
  const variantLabel = v => `${v.atlas_key} · ${v.resolution} · ${v.published_id ? 'Image '+v.published_id : 'not published'}`;
  const available = () => state.families.flatMap(f => f.variants || []);
  const names = v => [...new Set((v.consumers||[]).map(c => String(c.consumer_id||'').split(':')[0]).filter(Boolean))].sort();
  function draw() {
    const filter = (node('atlas-library-search').value || '').trim().toLowerCase();
    const variants = available().filter(v => !filter || `${v.atlas_key} ${v.filename} ${v.resolution} ${names(v).join(' ')}`.toLowerCase().includes(filter));
    node('atlas-library-count').textContent = String(available().length);
    node('atlas-library-list').innerHTML = variants.map(v => `<button type="button" class="atlas-library-item" data-atlas-open="${v.id}">
      <span><strong>${esc(v.filename)}</strong><small>${esc(v.resolution)} · ${esc(v.atlas_key)}</small>
        <small class="atlas-library-models">${names(v).length ? `Used by: ${names(v).map(esc).join(' · ')}` : 'No registered models use this variant'}</small></span>
      <span class="atlas-library-id">${v.published_id ? 'Image '+esc(v.published_id) : 'Local only'}</span>
      <span>${v.current ? 'Published' : (v.replacementPending ? 'Changed source' : 'Pending')}</span>
    </button>`).join('') || '<p class="muted">No atlases match the search.</p>';
    node('atlas-library-list').querySelectorAll('[data-atlas-open]').forEach(button => {
      button.onclick = () => openAtlas(Number(button.dataset.atlasOpen));
    });
  }
  async function load() {
    try {
      node('atlas-library-status').textContent = 'Loading atlases…';
      const data = await request('/api/texture-atlases');
      state.families = data.families || [];
      draw();
      node('atlas-library-status').textContent = '';
    } catch (error) {
      node('atlas-library-status').textContent = error.message;
    }
  }
  function updateControls() {
    const plan = state.active;
    if (!plan) return;
    const automatic = node('atlas-library-auto').checked;
    const selector = node('atlas-library-replacement');
    if (automatic && plan.suggestedReplacementId) selector.value = String(plan.suggestedReplacementId);
    selector.disabled = automatic || state.busy;
    const target = Number(selector.value || 0);
    node('atlas-library-retire').disabled = state.busy || !node('atlas-library-confirm').checked ||
      ((plan.consumers.length > 0 || automatic) && !target);
  }
  async function openAtlas(id) {
    state.busy = true;
    node('atlas-library-dialog-status').textContent = '';
    try {
      const plan = await request(`/api/texture-atlases/variants/${id}/retirement`);
      state.active = plan;
      const v = plan.variant;
      node('atlas-library-dialog-title').textContent = `${v.atlas_key} · ${v.resolution}`;
      node('atlas-library-dialog-summary').textContent = `${v.filename} · ${v.published_id ? 'Image ID '+v.published_id : 'Unpublished'} · variant ${v.id}`;
      node('atlas-library-consumers').innerHTML = (plan.consumers || []).map(c =>
        `<li><strong>${esc(c.consumer_type)}</strong> · ${esc(c.consumer_id)} <small>binding revision ${Number(c.revision)}</small></li>`
      ).join('') || '<li>Not used by any registered consumer.</li>';
      node('atlas-library-replacement').innerHTML = '<option value="">Choose published replacement</option>' +
        (plan.candidates || []).map(v => `<option value="${v.id}">${esc(variantLabel(v))}</option>`).join('');
      node('atlas-library-auto').checked = false;
      node('atlas-library-auto').disabled = !plan.suggestedReplacementId;
      // Select the same-model atlas family first; never silently propose a foreign texture.
      node('atlas-library-replacement').value = plan.suggestedReplacementId ? String(plan.suggestedReplacementId) : '';
      const suggestion = plan.candidates.find(v => v.id === plan.suggestedReplacementId);
      node('atlas-library-recommendation').textContent = suggestion
        ? `Closest quality in same atlas family: ${variantLabel(suggestion)}`
        : 'No alternate published resolution in this atlas family. Select a replacement manually.';
      node('atlas-library-confirm').checked = false;
      state.busy = false;
      updateControls();
      node('atlas-library-dialog').showModal();
    } catch (error) { state.active = null; state.busy = false; toast(error.message, true); }
  }
  async function retire() {
    if (!state.active || state.busy || node('atlas-library-retire').disabled) return;
    const plan = state.active;
    const automatic = node('atlas-library-auto').checked;
    const selected = Number(node('atlas-library-replacement').value || 0);
    state.busy = true; updateControls();
    node('atlas-library-dialog-status').textContent = 'Updating bindings and retaining history…';
    try {
      const result = await request(`/api/texture-atlases/variants/${plan.variant.id}/retire`, {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          token:plan.token,autoClosest:automatic,replacementVariantId:automatic || !selected ? null : selected,
        }),
      });
      node('atlas-library-dialog').close();
      state.active = null;
      await load();
      const warnings = result.exportWarnings || [];
      toast(warnings.length
        ? `Atlas archived; ${result.consumersRebound} bindings moved. Manifest export needs attention: ${warnings.join('; ')}`
        : `Atlas deleted from active library · ${result.consumersRebound} bindings moved · Studio Sync required for affected consumers`, Boolean(warnings.length));
    } catch (error) { node('atlas-library-dialog-status').textContent = error.message; toast(error.message, true); }
    finally { state.busy = false; updateControls(); }
  }
  node('atlas-library-refresh').onclick = load;
  node('atlas-library-search').oninput = draw;
  node('atlas-library-close').onclick = () => node('atlas-library-dialog').close();
  node('atlas-library-auto').onchange = updateControls;
  node('atlas-library-replacement').onchange = updateControls;
  node('atlas-library-confirm').onchange = updateControls;
  node('atlas-library-retire').onclick = retire;
  node('atlas-library-dialog').addEventListener('close', () => { state.active = null; });
  window.game1AtlasLibraryLoad = load;
  load();
})();
