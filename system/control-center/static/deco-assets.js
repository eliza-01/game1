const decoAssetState = {
  data: null,
  selected: null,
  modelPath: '',
  texturePath: '',
  textureReferenceSlug: '',
};

function decoAssetSelected() {
  return decoAssetState.data?.items?.find((row) => row.slug === decoAssetState.selected) || null;
}

function decoAssetSlugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .slice(0, 64);
}

function decoAssetCategoryLabel(category) {
  const item = decoAssetState.data?.options?.categories?.find((row) => row.id === category);
  return item?.label || category || '';
}

function decoAssetStatusTag(status) {
  return `<span class="tag ${String(status || '').toLowerCase()}">${esc(status || '')}</span>`;
}

function decoAssetSyncSlug() {
  if (!decoAssetState.selected) {
    $('location-asset-slug').value = decoAssetSlugify($('location-asset-name').value);
  }
}

function decoAssetSetForm(row) {
  decoAssetState.selected = row?.slug || null;
  decoAssetState.modelPath = '';
  decoAssetState.texturePath = '';
  decoAssetState.textureReferenceSlug = row?.texture_reference_slug || '';

  if (row) {
    $('location-asset-name').value = row.name_en || '';
    $('location-asset-slug').value = row.slug || '';
    $('location-asset-category').value = row.category || 'tree';
    $('location-asset-destructible').checked = row.destructible === true || Number(row.destructible || 0) === 1;
    $('picked-location-asset-model').textContent = 'keep current fbx or choose a replacement';
    $('picked-location-asset-texture').textContent = row.texture_shared
      ? `reusing ${row.texture_owner_slug || row.texture_reference_slug}`
      : 'keep current texture or choose a PNG/JPG replacement';
  } else {
    $('location-asset-name').value = '';
    $('location-asset-slug').value = '';
    $('location-asset-category').value = decoAssetState.data?.options?.categories?.[0]?.id || 'tree';
    $('location-asset-destructible').checked = false;
    $('picked-location-asset-model').textContent = 'fbx not selected';
    $('picked-location-asset-texture').textContent = 'PNG/JPG not selected';
  }

  decoAssetRender();
}

function decoAssetRenderTree() {
  const host = $('location-asset-tree');
  const items = decoAssetState.data?.items || [];
  host.innerHTML = '';

  for (const category of decoAssetState.data?.options?.categories || []) {
    const rows = items.filter((row) => row.category === category.id);
    if (!rows.length) continue;

    const group = document.createElement('div');
    group.className = 'deco-tree-group';
    group.innerHTML = `<small>${esc(category.label)}</small>`;
    host.appendChild(group);

    for (const row of rows) {
      const button = document.createElement('button');
      button.className = row.slug === decoAssetState.selected ? 'active' : '';
      button.innerHTML = `<span>${esc(row.name_en)}<small>${esc(row.slug)}</small></span><small>${esc(row.status)}</small>`;
      button.onclick = () => decoAssetSetForm(row);
      host.appendChild(button);
    }
  }

  if (!items.length) {
    host.innerHTML = '<span class="muted">no location assets.</span>';
  }
}

function decoAssetRenderTextureReferences() {
  const select = $('location-asset-texture-reference');
  const current = decoAssetState.textureReferenceSlug || '';
  const selectedSlug = decoAssetState.selected || '';
  select.innerHTML = '<option value="">own / new PNG/JPG texture</option>';
  for (const row of decoAssetState.data?.items || []) {
    if (row.slug === selectedSlug || row.texture_owner_slug !== row.slug) continue;
    if (!row.texture_source_path) continue;
    const option = document.createElement('option');
    option.value = row.texture_owner_slug;
    const owner = (decoAssetState.data?.items || []).find((item) => item.slug === row.texture_owner_slug) || row;
    option.textContent = `${owner.name_en || owner.slug} · ${owner.texture_asset_id || 'not published'}`;
    select.appendChild(option);
  }
  select.value = current;
}

function decoAssetRender() {
  if (!decoAssetState.data) return;

  const selected = decoAssetSelected();
  const summary = decoAssetState.data.summary || {};
  $('location-asset-rail-count').textContent = String(summary.registered || 0);
  $('location-asset-metric-total').textContent = String(summary.registered || 0);
  $('location-asset-metric-published').textContent = String(summary.published || 0);
  $('location-asset-metric-changed').textContent = String(summary.changed || 0);

  const categories = $('location-asset-category');
  if (!categories.options.length) {
    for (const category of decoAssetState.data.options?.categories || []) {
      const option = document.createElement('option');
      option.value = category.id;
      option.textContent = category.label;
      categories.appendChild(option);
    }
  }

  decoAssetRenderTree();
  decoAssetRenderTextureReferences();

  const publication = decoAssetState.data.publication || {};
  const publicationState = $('location-asset-publication-state');
  publicationState.className = publication.configured ? 'publication-ok' : 'publication-missing';
  publicationState.textContent = publication.configured ? 'open cloud: ready' : 'open cloud: not configured';

  const status = $('location-asset-model-status');
  if (selected) {
    const textureInfo = selected.texture_shared
      ? `shared texture from ${esc(selected.texture_owner_slug || selected.texture_reference_slug)} · ${esc(selected.texture_asset_id || 'not published')}`
      : `texture ${esc(selected.texture_asset_id || 'not published')}`;
    status.innerHTML = `<strong>${esc(selected.name_en)} · ${decoAssetStatusTag(selected.status)}</strong><span>${esc(decoAssetCategoryLabel(selected.category))} · model ${esc(selected.model_asset_id || 'not published')} · ${textureInfo}</span>`;
  } else {
    status.innerHTML = '<strong>not registered</strong><span>choose FBX + PNG/JPG, then register the location asset.</span>';
  }

  $('publish-location-asset').disabled = !selected || !publication.configured;
  $('delete-location-asset').disabled = !selected;
  $('location-asset-publication-hint').textContent = selected
    ? (selected.status === 'PUBLISHED'
      ? 'Published and available to DecoManager.'
      : 'Publish changed model/texture so DecoManager can load it.')
    : 'select a registered location asset.';

  const rows = $('location-asset-rows');
  rows.innerHTML = '';
  for (const row of decoAssetState.data.items || []) {
    const tr = document.createElement('tr');
    const contactPolicy = (row.destructible === true || Number(row.destructible || 0) === 1) ? '<span class="tag">destructible</span>' : '<span class="tag published">solid · bounce</span>';
    tr.innerHTML = `<td><b>${esc(row.name_en)}</b><small>${esc(row.slug)}</small></td><td>${esc(decoAssetCategoryLabel(row.category))}</td><td>${contactPolicy}</td><td><small>model ${esc(row.model_asset_id || '—')}</small><small>${row.texture_shared ? `shared ${esc(row.texture_owner_slug || row.texture_reference_slug)} · ` : 'texture '}${esc(row.texture_asset_id || '—')}</small></td><td>${decoAssetStatusTag(row.status)}</td><td><button data-select type="button">edit</button></td>`;
    tr.querySelector('[data-select]').onclick = () => decoAssetSetForm(row);
    rows.appendChild(tr);
  }
}

async function decoAssetLoad() {
  try {
    decoAssetState.data = await request('/api/location-assets');
    if (decoAssetState.selected && !decoAssetSelected()) {
      decoAssetState.selected = null;
    }
    decoAssetRender();
  } catch (error) {
    toast(error.message, true);
  }
}

async function decoAssetChooseModel() {
  try {
    const result = await request('/api/files/choose-location-asset-model', { method: 'POST' });
    if (!result.path) return;
    decoAssetState.modelPath = result.path;
    $('picked-location-asset-model').textContent = result.path;
  } catch (error) {
    toast(error.message, true);
  }
}

async function decoAssetChooseTexture() {
  try {
    const result = await request('/api/files/choose-location-asset-texture', { method: 'POST' });
    if (!result.path) return;
    decoAssetState.texturePath = result.path;
    decoAssetState.textureReferenceSlug = '';
    $('location-asset-texture-reference').value = '';
    $('picked-location-asset-texture').textContent = result.path;
  } catch (error) {
    toast(error.message, true);
  }
}

async function decoAssetRegister() {
  try {
    const selected = decoAssetSelected();
    const payload = {
      nameEn: $('location-asset-name').value.trim(),
      slug: $('location-asset-slug').value.trim(),
      category: $('location-asset-category').value,
      modelSourcePath: decoAssetState.modelPath,
      textureSourcePath: decoAssetState.texturePath,
      textureReferenceSlug: decoAssetState.textureReferenceSlug,
      destructible: $('location-asset-destructible').checked,
    };
    if (!selected && !payload.modelSourcePath) {
      throw Error('choose FBX');
    }
    if (!selected && !payload.textureSourcePath && !payload.textureReferenceSlug) {
      throw Error('choose PNG/JPG or reuse a registered texture');
    }

    const row = await request('/api/location-assets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    decoAssetState.selected = row.slug;
    await decoAssetLoad();
    decoAssetSetForm(decoAssetSelected());
    toast(`registered ${row.name_en}`);
  } catch (error) {
    toast(error.message, true);
  }
}

async function decoAssetPublish() {
  const row = decoAssetSelected();
  if (!row) return;
  try {
    toast('publishing location asset…');
    await request(`/api/location-assets/${encodeURIComponent(row.slug)}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: $('location-asset-publication-description').value }),
    });
    await decoAssetLoad();
    decoAssetSetForm(decoAssetSelected());
    toast('location asset published · DecoManager can refresh now');
  } catch (error) {
    toast(error.message, true);
  }
}

async function decoAssetDelete() {
  const row = decoAssetSelected();
  if (!row || !confirm(`delete ${row.name_en} from the game1 location asset registry? placed Studio instances are not removed.`)) {
    return;
  }
  try {
    await request(`/api/location-assets/${encodeURIComponent(row.slug)}`, { method: 'DELETE' });
    decoAssetState.selected = null;
    await decoAssetLoad();
    decoAssetSetForm(null);
    toast('location asset registry row deleted');
  } catch (error) {
    toast(error.message, true);
  }
}

window.game1LocationAssetsLoad = decoAssetLoad;
$('location-asset-name').oninput = decoAssetSyncSlug;
$('new-location-asset').onclick = () => decoAssetSetForm(null);
$('refresh-location-assets').onclick = decoAssetLoad;
$('refresh-location-assets-table').onclick = decoAssetLoad;
$('choose-location-asset-model').onclick = decoAssetChooseModel;
$('choose-location-asset-texture').onclick = decoAssetChooseTexture;
$('location-asset-texture-reference').onchange = () => {
  decoAssetState.textureReferenceSlug = $('location-asset-texture-reference').value;
  if (decoAssetState.textureReferenceSlug) {
    decoAssetState.texturePath = '';
    $('picked-location-asset-texture').textContent = `reusing ${decoAssetState.textureReferenceSlug}`;
  } else if (!decoAssetState.selected) {
    $('picked-location-asset-texture').textContent = 'PNG/JPG not selected';
  }
};
$('register-location-asset').onclick = decoAssetRegister;
$('clear-location-asset-form').onclick = () => decoAssetSetForm(null);
$('publish-location-asset').onclick = decoAssetPublish;
$('delete-location-asset').onclick = decoAssetDelete;
