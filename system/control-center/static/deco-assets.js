const decoAssetState = {
  data: null,
  selected: null,
  modelPath: '',
  texturePath: '',
  textureReferenceSlug: '',
  atlasVariantId: 0,
  replacementPath: '',
  atlasBusy: false,
  libraryCategory: 'all',
};

const DECO_LIBRARY_CATEGORY_KEY = 'game1.locationAssets.libraryCategory';
const DECO_SELECTED_ASSET_KEY = 'game1.locationAssets.selectedAsset';

function decoAssetRemember(key, value) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {}
}

function decoAssetRestorePreferences() {
  try {
    decoAssetState.libraryCategory = localStorage.getItem(DECO_LIBRARY_CATEGORY_KEY) || 'all';
    decoAssetState.selected = localStorage.getItem(DECO_SELECTED_ASSET_KEY) || null;
  } catch {}
}

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

// The API resolves shared textures to the canonical owner. Only fall back to
// its canonical path for records registered before filename metadata existed.
function decoAssetTextureFilename(row) {
  return row?.texture_filename || String(row?.texture_path || '').split(/[\\/]/).pop() || '';
}

function decoAssetStatusTag(status) {
  return `<span class="tag ${String(status || '').toLowerCase()}">${esc(status || '')}</span>`;
}

function decoAssetSyncSlug() {
  game1SyncPublicationDescription("location-asset-publication-description", "Location Asset", $("location-asset-name").value);
  if (!decoAssetState.selected) {
    $('location-asset-slug').value = decoAssetSlugify($('location-asset-name').value);
  }
}

function decoAssetBeginNew() {
  decoAssetSetForm(null);
  const input = $('location-asset-name');
  if (input) input.focus();
}

function decoAssetSetForm(row) {
  decoAssetState.selected = row?.slug || null;
  decoAssetRemember(DECO_SELECTED_ASSET_KEY, decoAssetState.selected || '');
  decoAssetState.modelPath = '';
  decoAssetState.texturePath = '';
  decoAssetState.replacementPath = '';
  decoAssetState.textureReferenceSlug = row?.atlasVariantId ? '' : (row?.texture_reference_slug || '');
  decoAssetState.atlasVariantId = Number(row?.atlasVariantId || 0);

  if (row) {
    $('location-asset-name').value = row.name_en || '';
    $('location-asset-slug').value = row.slug || '';
    $('location-asset-category').value = row.category || 'tree';
    decoAssetState.libraryCategory = row.category || 'tree';
    decoAssetRemember(DECO_LIBRARY_CATEGORY_KEY, decoAssetState.libraryCategory);
    $('location-asset-destructible').checked = row.destructible === true || Number(row.destructible || 0) === 1;
    $('picked-location-asset-model').textContent = 'keep current fbx or choose a replacement';
    $('picked-location-asset-texture').textContent = row.texture_shared
      ? `legacy reuse ${row.texture_owner_slug || row.texture_reference_slug} · ${decoAssetTextureFilename(row)}`
      : `${decoAssetTextureFilename(row) || 'no texture'} · keep or choose a PNG/JPG replacement`;
  } else {
    $('location-asset-name').value = '';
    $('location-asset-slug').value = '';
    const validCategories = new Set((decoAssetState.data?.options?.categories || []).map((item) => item.id));
    const category = validCategories.has(decoAssetState.libraryCategory)
      ? decoAssetState.libraryCategory
      : (decoAssetState.data?.options?.categories?.[0]?.id || 'tree');
    $('location-asset-category').value = category;
    $('location-asset-destructible').checked = false;
    $('picked-location-asset-model').textContent = 'fbx not selected';
    $('picked-location-asset-texture').textContent = 'PNG/JPG not selected';
  }

  game1SyncPublicationDescription("location-asset-publication-description", "Location Asset", row?.name_en || "");
  decoAssetRender();
}

// An atlas family/size is one variant, regardless of which models reuse it.
// A changed file with the same canonical filename selects that variant for
// Republish instead of pretending to be a new model-owned texture.
function decoAssetMatchingVariant(path) {
  const filename = String(path || '').split(/[\\/]/).pop();
  const match = filename.match(/^(.+)_([1-9][0-9]*)x([1-9][0-9]*)_atlas\.(png|jpe?g)$/i);
  if (!match) return null;
  const family = (decoAssetState.data?.atlases || []).find(
    (item) => item.atlasKey.toLowerCase() === match[1].toLowerCase());
  return family?.variants?.find(
    (variant) => Number(variant.width) === Number(match[2])
      && Number(variant.height) === Number(match[3])) || null;
}

function decoAssetAtlasRepublishMode() {
  const variant = (decoAssetState.data?.atlases || []).flatMap((group) => group.variants || [])
    .find((item) => Number(item.id) === decoAssetState.atlasVariantId);
  return Boolean(decoAssetState.replacementPath || variant?.replacementPending);
}

// Legacy compatibility: can still reuse a registered texture by owner slug.
// A single catalog is shared by every Location Asset. Never list owners as
// independent copies of the same published atlas variant.
function decoAssetRenderTextureReferences() {
  const select = $('location-asset-texture-reference');
  const query = $('location-asset-atlas-search').value.trim().toLowerCase();
  const selectedValue = decoAssetState.atlasVariantId
    ? `variant:${decoAssetState.atlasVariantId}`
    : (decoAssetState.textureReferenceSlug ? `legacy:${decoAssetState.textureReferenceSlug}` : '');
  select.innerHTML = '<option value="">own / new PNG/JPG atlas</option>';
  for (const family of decoAssetState.data?.atlases || []) {
    const group = document.createElement('optgroup');
    group.label = family.atlasKey;
    for (const variant of family.variants || []) {
      if (query && !`${family.atlasKey} ${variant.resolution} ${variant.filename}`.toLowerCase().includes(query)
          && Number(variant.id) !== decoAssetState.atlasVariantId) continue;
      const option = document.createElement('option');
      option.value = `variant:${variant.id}`;
      option.textContent = `${variant.resolution} · ${variant.filename} · ${variant.current ? variant.published_id : 'publish required'}`;
      group.appendChild(option);
    }
    if (group.children.length) select.appendChild(group);
  }
  const legacy = document.createElement('optgroup');
  legacy.label = 'Legacy texture reuse (compatibility only)';
  for (const row of decoAssetState.data?.items || []) {
    if (row.slug === decoAssetState.selected || row.atlasVariantId || row.texture_owner_slug !== row.slug || !row.texture_path) continue;
    if (query && !`${row.slug} ${decoAssetTextureFilename(row)}`.toLowerCase().includes(query)) continue;
    const option = document.createElement('option');
    option.value = `legacy:${row.slug}`;
    option.textContent = `${decoAssetTextureFilename(row)} · ${row.texture_asset_id || 'unpublished'} (legacy)`;
    legacy.appendChild(option);
  }
  if (legacy.children.length) select.appendChild(legacy);
  select.value = selectedValue;
  const republish = decoAssetAtlasRepublishMode();
  const publishButton = $('publish-location-atlas-variant');
  publishButton.textContent = republish ? 'Republish atlas · new Roblox ID' : 'Publish selected atlas';
  publishButton.disabled = decoAssetState.atlasBusy || !decoAssetState.atlasVariantId || !decoAssetState.data?.publication?.configured;
  $('register-location-atlas-variant').disabled = decoAssetState.atlasBusy || !decoAssetState.texturePath;

}

const DECO_ATLAS_COLORS = ['#d9ac43', '#a47bdf', '#4f95ee', '#54b991', '#939ba8'];

function decoAtlasWarning(row) {
  return row.atlasLegacyWarning
    ? `<span class="deco-atlas-warning" title="Legacy filename. Expected &lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png" aria-label="Legacy atlas filename">⚠️</span>`
    : '';
}

function decoAtlasDots(row) {
  // Gold is always leftmost: rank by actual pixel count, not insertion order.
  const variants = [...(row.atlasVariants || [])].sort((a, b) =>
    (Number(b.width) * Number(b.height) - Number(a.width) * Number(a.height)) ||
    (Number(b.width) - Number(a.width)) ||
    (Number(b.height) - Number(a.height)) ||
    (Number(a.id) - Number(b.id))
  );
  if (!variants.length) return '';
  const render = (variant, index) => {
    const current = Number(row.atlasVariantId) === Number(variant.id);
    const valid = Boolean(variant.current);
    const tip = `${variant.filename} · ${variant.resolution}${valid ? '' : ' · publish first'}`;
    return `<button type="button" class="deco-atlas-dot ${current ? 'is-active' : ''}" style="--dot-color:${DECO_ATLAS_COLORS[Math.min(index,4)]}" data-atlas-variant="${Number(variant.id)}" title="${esc(tip)}" aria-label="${esc(tip)}" aria-pressed="${current}" ${(!valid || decoAssetState.atlasBusy) ? 'disabled' : ''}><span></span></button>`;
  };
  return `<div class="deco-atlas-dots" aria-label="Registered atlas resolutions">${variants.slice(0,5).map(render).join('')}${variants.length>5 ? `<details class="deco-atlas-more"><summary>+${variants.length-5}</summary><div>${variants.slice(5).map((v,i)=>render(v,i+5)).join('')}</div></details>` : ''}</div>`;
}

async function decoAssetChooseAtlasVariant(row, id) {
  if (decoAssetState.atlasBusy || Number(row.atlasVariantId) === Number(id)) return;
  decoAssetState.atlasBusy = true;
  decoAssetRender();
  try {
    await request(`/api/location-assets/${encodeURIComponent(row.slug)}/atlas-binding`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({variantId: id, expectedRevision: Number(row.bindingRevision || 0)}),
    });
    await decoAssetLoad();
    await decoAssetRetrySync(row.slug);
  } catch (error) {
    toast(`Atlas change: ${error.message}`, true);
    await decoAssetLoad();
  } finally {
    decoAssetState.atlasBusy = false;
    decoAssetRender();
  }
}

async function decoAssetRetrySync(slug) {
  try {
    const result = await request('/api/location-assets/studio-sync', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug}),
    });
    toast(`Studio synced · ${Number(result.studio?.matchedModels || 0)} matched · ${Number(result.studio?.parts || 0)} parts updated. Save Place in Studio.`);
  } catch (error) {
    toast(`Atlas saved; Studio sync pending: ${error.message}. Use Retry.`, true);
  }
  await decoAssetLoad();
}

function decoAssetUseCategory(category, { updateEditor = true } = {}) {
  const categories = decoAssetState.data?.options?.categories || [];
  if (!categories.some((row) => row.id === category)) return;
  decoAssetState.libraryCategory = category;
  decoAssetRemember(DECO_LIBRARY_CATEGORY_KEY, category);
  if (updateEditor) $('location-asset-category').value = category;
}

function decoAssetRenderLibraryFilter() {
  const select = $('location-asset-library-category');
  if (!select) return;
  const categories = decoAssetState.data?.options?.categories || [];
  const valid = new Set(['all', ...categories.map((row) => row.id)]);
  if (!valid.has(decoAssetState.libraryCategory)) decoAssetState.libraryCategory = 'all';
  select.innerHTML = '<option value="all">all categories</option>';
  for (const category of categories) {
    const option = document.createElement('option');
    option.value = category.id;
    option.textContent = category.label;
    select.appendChild(option);
  }
  select.value = decoAssetState.libraryCategory;
}

function decoAssetRender() {
  if (!decoAssetState.data) return;

  const selected = decoAssetSelected();
  const summary = decoAssetState.data.summary || {};
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

  decoAssetRenderTextureReferences();
  decoAssetRenderLibraryFilter();
  $('register-location-asset').textContent = selected ? 'save asset changes' : 'register asset';

  const publication = decoAssetState.data.publication || {};
  const publicationState = $('location-asset-publication-state');
  publicationState.className = publication.configured ? 'publication-ok' : 'publication-missing';
  publicationState.textContent = publication.configured ? 'open cloud: ready' : 'open cloud: not configured';

  const status = $('location-asset-model-status');
  if (selected) {
    const textureInfo = selected.texture_shared
      ? `shared texture from ${esc(selected.texture_owner_slug || selected.texture_reference_slug)} · ${esc(decoAssetTextureFilename(selected))} · ${esc(selected.texture_asset_id || 'not published')}`
      : `texture ${esc(decoAssetTextureFilename(selected))} · ${esc(selected.texture_asset_id || 'not published')}`;
    status.innerHTML = `<strong>${esc(selected.name_en)} ${decoAtlasWarning(selected)} · ${decoAssetStatusTag(selected.status)}</strong><span>${esc(decoAssetCategoryLabel(selected.category))} · model ${esc(selected.model_asset_id || 'not published')} · ${textureInfo}</span>`;
  } else {
    status.innerHTML = '<strong>not registered</strong><span>choose FBX + PNG/JPG, then register the location asset.</span>';
  }

  $('publish-location-asset').disabled = !selected || !publication.configured;
  $('sync-location-assets').disabled = !(decoAssetState.data.items || []).some(row => row.status === 'PUBLISHED');
  $('delete-location-asset').disabled = !selected;
  $('location-asset-publication-hint').textContent = selected
    ? (selected.status === 'PUBLISHED'
      ? 'Published and available to DecoManager.'
      : 'Publish changed model/texture so DecoManager can load it.')
    : 'select a registered location asset.';

  const rows = $('location-asset-rows');
  rows.innerHTML = '';
  const libraryRows = (decoAssetState.data.items || []).filter((row) =>
    decoAssetState.libraryCategory === 'all' || row.category === decoAssetState.libraryCategory
  );
  for (const row of libraryRows) {
    const tr = document.createElement('tr');
    const contactPolicy = (row.destructible === true || Number(row.destructible || 0) === 1) ? '<span class="tag">destructible</span>' : '<span class="tag published">solid · bounce</span>';
    tr.innerHTML = `<td><b>${esc(row.name_en)}</b><small>${esc(row.slug)}</small><small class="deco-texture-filename">${esc(decoAssetTextureFilename(row) || 'no texture')} ${decoAtlasWarning(row)}</small>${decoAtlasDots(row)}${row.studioSyncStatus === 'pending_studio_sync' ? '<button class="deco-atlas-retry" data-retry type="button">Sync pending · retry</button>' : ''}</td><td>${esc(decoAssetCategoryLabel(row.category))}</td><td>${contactPolicy}</td><td><small>model ${esc(row.model_asset_id || '—')}</small><small>${row.texture_shared ? `shared ${esc(row.texture_owner_slug || row.texture_reference_slug)} · ` : 'texture '}${esc(row.texture_asset_id || '—')}</small></td><td>${decoAssetStatusTag(row.status)}</td><td><button data-select type="button">edit</button></td>`;
    tr.querySelector('[data-select]').onclick = () => decoAssetSetForm(row);
    tr.querySelectorAll('[data-atlas-variant]').forEach((button) => {
      button.onclick = () => decoAssetChooseAtlasVariant(row, Number(button.dataset.atlasVariant));
    });
    const retry = tr.querySelector('[data-retry]');
    if (retry) retry.onclick = () => decoAssetRetrySync(row.slug);
    rows.appendChild(tr);
  }
  if (!libraryRows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6"><span class="muted">no registered assets in ${esc(decoAssetState.libraryCategory === 'all' ? 'the library' : decoAssetCategoryLabel(decoAssetState.libraryCategory))}.</span></td>`;
    rows.appendChild(tr);
  }
}

async function decoAssetLoad() {
  try {
    decoAssetState.data = await request('/api/location-assets');
    if (decoAssetState.selected && !decoAssetSelected()) {
      decoAssetState.selected = null;
      decoAssetRemember(DECO_SELECTED_ASSET_KEY, '');
    }
    const selected = decoAssetSelected();
    if (selected) {
      decoAssetSetForm(selected);
    } else {
      decoAssetRender();
      const categories = new Set((decoAssetState.data?.options?.categories || []).map((row) => row.id));
      if (categories.has(decoAssetState.libraryCategory)) {
        $('location-asset-category').value = decoAssetState.libraryCategory;
      }
    }
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
    const matched = decoAssetMatchingVariant(result.path);
    decoAssetState.texturePath = matched ? '' : result.path;
    decoAssetState.replacementPath = matched ? result.path : '';
    decoAssetState.textureReferenceSlug = '';
    decoAssetState.atlasVariantId = matched ? Number(matched.id) : 0;
    $('picked-location-asset-texture').textContent = matched
      ? `Republish candidate · ${result.path} · current Roblox ID ${matched.published_id || 'not published'}`
      : result.path;
    decoAssetRenderTextureReferences();
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
      atlasVariantId: decoAssetState.atlasVariantId,
      destructible: $('location-asset-destructible').checked,
    };
    if (!selected && !payload.modelSourcePath) {
      throw Error('choose FBX');
    }
    if (!selected && !payload.textureSourcePath && !payload.textureReferenceSlug && !payload.atlasVariantId) {
      throw Error('choose PNG/JPG or a registered atlas variant');
    }

    const row = await request('/api/location-assets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    decoAssetState.selected = row.slug;
    await decoAssetLoad();
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
    const published = await request(`/api/location-assets/${encodeURIComponent(row.slug)}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: $('location-asset-publication-description').value }),
    });
    await decoAssetLoad();
    toast(`location asset published · model ${published.model_asset_id || '—'} · texture ${published.texture_asset_id || '—'}`);
  } catch (error) {
    toast(error.message, true);
  }
}

// DecoManager is the owner of Studio placement. Sync refreshes its registry
// and rebinds the material on placed instances; it never imports duplicates.
async function decoAssetSyncStudio() {
  const button = $('sync-location-assets');
  if (button.disabled) return;
  button.disabled = true;
  try {
    toast('syncing DecoManager and placed asset textures in Studio…');
    const result = await request('/api/location-assets/studio-sync', { method: 'POST' });
    const studio = result.studio || {};
    toast(`Studio synced · ${Number(studio.models || 0)} placed model(s), ${Number(studio.parts || 0)} MeshPart(s) updated · ${Number(studio.registryItems || 0)} registered`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    decoAssetRender();
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

decoAssetRestorePreferences();
window.game1LocationAssetsLoad = decoAssetLoad;
$('location-asset-name').oninput = decoAssetSyncSlug;
$('new-location-asset-main').onclick = decoAssetBeginNew;
$('refresh-location-assets-table').onclick = decoAssetLoad;
$('choose-location-asset-model').onclick = decoAssetChooseModel;
$('choose-location-asset-texture').onclick = decoAssetChooseTexture;
$('location-asset-atlas-search').oninput = decoAssetRenderTextureReferences;
$('location-asset-texture-reference').onchange = () => {
  const selection = $('location-asset-texture-reference').value;
  decoAssetState.atlasVariantId = selection.startsWith('variant:') ? Number(selection.slice(8)) : 0;
  decoAssetState.textureReferenceSlug = selection.startsWith('legacy:') ? selection.slice(7) : '';
  decoAssetState.replacementPath = '';
  if (selection) {
    decoAssetState.texturePath = '';
    $('picked-location-asset-texture').textContent = `using ${$('location-asset-texture-reference').selectedOptions[0].textContent}`;
  }
  decoAssetRenderTextureReferences();
};
$('register-location-atlas-variant').onclick = async () => {
  if (!decoAssetState.texturePath) return toast('Choose PNG/JPG first', true);
  try {
    const variant = await request('/api/texture-atlases/variants', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({sourcePath:decoAssetState.texturePath}),
    });
    decoAssetState.texturePath = '';
    decoAssetState.replacementPath = '';
    decoAssetState.atlasVariantId = variant.id;
    decoAssetState.textureReferenceSlug = '';
    await decoAssetLoad();
    toast(`Atlas variant registered · ${variant.atlas_key} ${variant.resolution}`);
  } catch (error) { toast(error.message, true); }
};
$('publish-location-atlas-variant').onclick = async () => {
  if (!decoAssetState.atlasVariantId || decoAssetState.atlasBusy) return;
  const id = decoAssetState.atlasVariantId;
  const path = decoAssetState.replacementPath;
  const republish = decoAssetAtlasRepublishMode();
  if (republish && !confirm('Republish this atlas? Roblox will assign a NEW Image Asset ID. All models using this resolution will switch to the new ID.')) return;
  decoAssetState.atlasBusy = true;
  decoAssetRenderTextureReferences();
  try {
    const result = await request(`/api/texture-atlases/variants/${id}/${republish ? 'republish' : 'publish'}`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(republish ? {sourcePath:path} : {}),
    });
    decoAssetState.replacementPath = '';
    await decoAssetLoad();
    if (republish) {
      if (result.unchanged) toast('Atlas bytes unchanged · existing Image Asset ID kept (no upload)');
      else {
        const message = `Atlas republished · NEW Roblox Image ID ${result.variant.published_id} · ${result.syncedConsumers || 0} Studio sync(s) · ${result.pendingConsumers || 0} pending`;
        toast(result.studioErrors?.length ? `${message} · ${result.studioErrors.join('; ')}` : message, Boolean(result.studioErrors?.length));
      }
    } else toast(`Atlas published · Roblox Image ID ${result.published_id}`);
  } catch (error) {
    toast(`Atlas publication: ${error.message}`, true);
    await decoAssetLoad();
  } finally {
    decoAssetState.atlasBusy = false;
    decoAssetRenderTextureReferences();
  }
};
$('location-asset-library-category').onchange = () => {
  const category = $('location-asset-library-category').value || 'all';
  if (category === 'all') {
    decoAssetState.libraryCategory = 'all';
    decoAssetRemember(DECO_LIBRARY_CATEGORY_KEY, 'all');
  } else {
    decoAssetUseCategory(category);
  }
  decoAssetRender();
};
$('location-asset-category').onchange = () => {
  decoAssetUseCategory($('location-asset-category').value, { updateEditor: false });
  decoAssetRender();
};
$('register-location-asset').onclick = decoAssetRegister;
$('clear-location-asset-form').onclick = decoAssetBeginNew;
$('publish-location-asset').onclick = decoAssetPublish;
$('sync-location-assets').onclick = decoAssetSyncStudio;
$('delete-location-asset').onclick = decoAssetDelete;
