/* Location Assets: registration/library adapter.
 * Existing-resource editing lives in location-asset-workflow.js; the shared
 * Atlas Registry and Studio Sync own their respective domain operations.
 */
const decoAssetState = {
  data: null, modelPath: '', texturePath: '', atlasVariantId: 0,
  inspection: null, meshOptions: {},
  libraryCategory: 'all', syncingSlug: null, atlasBusy: false,
};
const DECO_LIBRARY_CATEGORY_KEY = 'game1.locationAssets.libraryCategory';
const DECO_ATLAS_COLORS = ['#d9ac43', '#a47bdf', '#4f95ee', '#54b991', '#939ba8'];

function decoAssetRemember(key, value) {
  try { if (value) localStorage.setItem(key, value); else localStorage.removeItem(key); } catch {}
}
function decoAssetRestorePreferences() {
  try { decoAssetState.libraryCategory = localStorage.getItem(DECO_LIBRARY_CATEGORY_KEY) || 'all'; } catch {}
}
function decoAssetSlugify(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '').replace(/_+/g, '_').slice(0, 64);
}
function decoAssetRow(slug) {
  return decoAssetState.data?.items?.find(item => item.slug === slug) || null;
}
function decoAssetCategoryLabel(category) {
  const item = decoAssetState.data?.options?.categories?.find(row => row.id === category);
  return item?.label || category || '';
}
function decoAssetTextureFilename(row) {
  return row?.texture_filename || String(row?.texture_path || '').split(/[\\/]/).pop() || '';
}
function decoAssetStatusTag(status) {
  return `<span class="tag ${String(status || '').toLowerCase()}">${esc(status || '')}</span>`;
}
function decoAssetSyncSlug() {
  $('location-asset-slug').value = decoAssetSlugify($('location-asset-name').value);
}
function decoAssetSetForm() {
  // The registration editor is always new-only, never a recycled Edit modal.
  decoAssetState.modelPath = '';
  decoAssetState.inspection = null;
  decoAssetState.meshOptions = {};
  decoAssetState.texturePath = '';
  decoAssetState.atlasVariantId = 0;
  $('location-asset-name').value = '';
  $('location-asset-slug').value = '';
  const categories = decoAssetState.data?.options?.categories || [];
  $('location-asset-category').value = categories.some(c => c.id === decoAssetState.libraryCategory)
    ? decoAssetState.libraryCategory : (categories[0]?.id || 'tree');
  $('location-asset-destructible').checked = false;
  $('location-asset-surface-material').value = 'default';
  window.game1LocationCategoryPicker?.refresh($('location-asset-category'));
  $('picked-location-asset-model').textContent = 'Choose the FBX for this new asset';
  decoAssetRenderInspection();
  $('picked-location-asset-texture').textContent = 'Choose PNG/JPG or reuse a registered atlas';
  $('location-asset-atlas-search').value = '';
  decoAssetRenderTextureReferences();
}
function decoAssetBeginNew() {
  decoAssetSetForm();
  $('location-asset-name').focus();
}
function decoAssetMatchingVariant(path) {
  const filename = String(path || '').split(/[\\/]/).pop();
  const match = filename.match(/^(.+)_([1-9][0-9]*)x([1-9][0-9]*)_atlas\.(png|jpe?g)$/i);
  if (!match) return null;
  const family = (decoAssetState.data?.atlases || []).find(
    group => group.atlasKey.toLowerCase() === match[1].toLowerCase());
  return family?.variants?.find(variant => Number(variant.width) === Number(match[2])
    && Number(variant.height) === Number(match[3])) || null;
}
function decoAssetRenderTextureReferences() {
  const select = $('location-asset-texture-reference');
  const query = $('location-asset-atlas-search').value.trim().toLowerCase();
  select.innerHTML = '<option value="">New local PNG/JPG atlas</option>';
  for (const family of decoAssetState.data?.atlases || []) {
    const group = document.createElement('optgroup');
    group.label = window.game1AtlasIdentity.describe({atlasKey:family.atlasKey}).key;
    for (const variant of family.variants || []) {
      if (query && !`${family.atlasKey} ${variant.resolution} ${variant.filename}`.toLowerCase().includes(query)
          && Number(variant.id) !== decoAssetState.atlasVariantId) continue;
      const option = document.createElement('option');
      option.value = `variant:${variant.id}`;
      option.textContent = window.game1AtlasIdentity.label({
        filename:variant.filename, atlasKey:family.atlasKey, resolution:variant.resolution,
      }, {assetId:variant.current ? variant.published_id : 'publish required'});
      group.appendChild(option);
    }
    if (group.children.length) select.appendChild(group);
  }
  select.value = decoAssetState.atlasVariantId ? `variant:${decoAssetState.atlasVariantId}` : '';
}
function decoAtlasWarning(row) {
  return row.atlasLegacyWarning
    ? '<span class="deco-atlas-warning" title="Legacy filename; expected &lt;atlas_key&gt;_&lt;width&gt;x&lt;height&gt;_atlas.png">⚠️</span>'
    : '';
}
function decoAtlasDots(row) {
  const variants = [...(row.atlasVariants || [])].sort((a,b) =>
    (Number(b.width)*Number(b.height) - Number(a.width)*Number(a.height)) ||
    (Number(b.width)-Number(a.width)) || (Number(b.height)-Number(a.height)) ||
    (Number(a.id)-Number(b.id)));
  if (!variants.length) return '';
  const render = (variant,index) => {
    const current = Number(row.atlasVariantId) === Number(variant.id);
    const valid = Boolean(variant.current);
    const tip = `${variant.filename} · ${variant.resolution}${valid?'':' · publish first'}`;
    return `<button type="button" class="deco-atlas-dot ${current?'is-active':''}" style="--dot-color:${DECO_ATLAS_COLORS[Math.min(index,4)]}" data-atlas-variant="${Number(variant.id)}" title="${esc(tip)}" aria-label="${esc(tip)}" aria-pressed="${current}" ${(!valid || decoAssetState.atlasBusy) ? 'disabled' : ''}><span></span></button>`;
  };
  return `<div class="deco-atlas-dots" aria-label="Registered atlas resolutions">${variants.slice(0,5).map(render).join('')}${variants.length>5 ? `<details class="deco-atlas-more"><summary>+${variants.length-5}</summary><div>${variants.slice(5).map((v,i)=>render(v,i+5)).join('')}</div></details>` : ''}</div>`;
}
async function decoAssetChooseAtlasVariant(row, id) {
  if (decoAssetState.atlasBusy || Number(row.atlasVariantId) === Number(id)) return null;
  decoAssetState.atlasBusy = true;
  decoAssetRender();
  try {
    const result = await request(`/api/location-assets/${encodeURIComponent(row.slug)}/atlas-binding`, {
      method: 'PUT', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({variantId:id, expectedRevision:Number(row.bindingRevision || 0)}),
    });
    await decoAssetLoad();
    toast(`Atlas binding saved for ${row.slug} · Sync Studio explicitly when ready.`);
    return result;
  } catch (error) {
    toast(`Atlas change: ${error.message}`, true);
    await decoAssetLoad();
    return null;
  } finally {
    decoAssetState.atlasBusy = false;
    decoAssetRender();
  }
}
function decoAssetUseCategory(category, {updateEditor = true} = {}) {
  if (!(decoAssetState.data?.options?.categories || []).some(c => c.id === category)) return;
  decoAssetState.libraryCategory = category;
  decoAssetRemember(DECO_LIBRARY_CATEGORY_KEY, category);
  if (updateEditor) { $('location-asset-category').value = category;
    window.game1LocationCategoryPicker?.refresh($('location-asset-category')); }
}
function decoAssetRenderLibraryFilter() {
  const filter = $('location-asset-library-category');
  filter.innerHTML = '<option value="all">all categories</option>';
  for (const category of decoAssetState.data?.options?.categories || []) {
    const option = document.createElement('option');
    option.value = category.id;
    option.textContent = category.label;
    filter.appendChild(option);
  }
  if (!['all', ...(decoAssetState.data?.options?.categories || []).map(c => c.id)].includes(decoAssetState.libraryCategory)) {
    decoAssetState.libraryCategory = 'all';
  }
  filter.value = decoAssetState.libraryCategory;
  window.game1LocationCategoryPicker?.mount(filter, decoAssetState.data?.options);
}
function decoAssetRender() {
  if (!decoAssetState.data) return;
  const summary = decoAssetState.data.summary || {};
  $('location-asset-metric-total').textContent = String(summary.registered || 0);
  $('location-asset-metric-published').textContent = String(summary.published || 0);
  $('location-asset-metric-changed').textContent = String(summary.changed || 0);
  const categories = $('location-asset-category');
  if (!categories.options.length) {
    for (const category of decoAssetState.data.options?.categories || []) {
      const option = document.createElement('option');
      option.value = category.id; option.textContent = category.label; categories.appendChild(option);
    }
    categories.value = categories[0]?.value || 'tree';
  }
  window.game1LocationCategoryPicker?.mount(categories, decoAssetState.data?.options);
  const materials=$('location-asset-surface-material');
  if(!materials.options.length){
    for(const material of decoAssetState.data.options?.surfaceMaterials||[]){
      const opt=document.createElement('option');opt.value=material.id;opt.textContent=material.label;
      materials.appendChild(opt);
    }
    materials.value='default';
  }
  decoAssetRenderTextureReferences();
  decoAssetRenderLibraryFilter();
  const publication = decoAssetState.data.publication || {};
  const publicationState = $('location-asset-publication-state');
  publicationState.className = publication.configured ? 'publication-ok' : 'publication-missing';
  publicationState.textContent = publication.configured ? 'open cloud: ready' : 'open cloud: not configured';
  const rows = $('location-asset-rows');
  rows.innerHTML = '';
  const visible = (decoAssetState.data.items || []).filter(row =>
    decoAssetState.libraryCategory === 'all' || row.category === decoAssetState.libraryCategory);
  for (const row of visible) {
    const tr = document.createElement('tr');
    const contactPolicy = row.destructible
      ? '<span class="tag">destructible</span>' : '<span class="tag published">solid · bounce</span>';
    const visualMeshes=row.publishedVisualMeshes||[];
    const meshLabels=visualMeshes.length?visualMeshes.map((mesh,i)=>
      `<small>Model ${i+1} · ${esc(mesh.name)} · Mesh ID ${esc(mesh.meshId)}</small>`).join(''):
      `<small class="muted">Mesh ID: нет данных · Find Mesh IDs в Studio</small>`;
    tr.innerHTML = `<td><b>${esc(row.name_en)}</b><small>${esc(row.slug)}</small>` +
      `<small class="deco-texture-filename">${esc(window.game1AtlasIdentity.describe({filename:decoAssetTextureFilename(row),atlasKey:row.atlasFamily||''}).key)} ${decoAtlasWarning(row)}</small>` +
      `${decoAtlasDots(row)}${row.studioSyncStatus === 'pending_studio_sync' ? '<small class="deco-sync-pending">Studio Sync pending</small>' : ''}</td>` +
      `<td>${esc(decoAssetCategoryLabel(row.category))}<small>${esc(row.materialDefinition?.label||'Default')}</small></td><td>${contactPolicy}</td>` +
      `<td><small>Model ID ${esc(row.model_asset_id || '—')}</small>${row.model_asset_id?meshLabels:''}<small>Image ID ${esc(row.texture_asset_id || '—')}</small></td>` +
      `<td>${decoAssetStatusTag(row.status)}</td><td><div class="deco-asset-row-actions">` +
      `<button data-select type="button" ${decoAssetState.syncingSlug?'disabled':''}>Edit</button>` +
      `<button data-deco-sync type="button" ${decoAssetState.syncingSlug || decoAssetState.atlasBusy ? 'disabled' : ''} title="Find placed models and sync the latest published Model and Atlas IDs for this slug. Unpublished resources are reported after opening instead of disabling the action.">Sync Studio</button>` +
      `</div></td>`;
    tr.querySelector('[data-select]').onclick = () => decoAssetEditOpen(row.slug);
    tr.querySelector('[data-deco-sync]').onclick = () => window.game1LocationAssetWorkflow.startScan(row.slug);
    tr.querySelectorAll('[data-atlas-variant]').forEach(button => {
      button.onclick = () => decoAssetChooseAtlasVariant(row, Number(button.dataset.atlasVariant));
    });
    rows.appendChild(tr);
  }
  if (!visible.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="6"><span class="muted">No registered assets match this category.</span></td>';
    rows.appendChild(tr);
  }
}
async function decoAssetLoad() {
  try {
    decoAssetState.data = await request('/api/location-assets');
    decoAssetRender();
  } catch (error) { toast(`Location Assets: ${error.message}`, true); }
}
function decoAssetRenderInspection() {
  const host=$('location-asset-fbx-preview');
  if(!host)return;
  host.innerHTML=window.game1MeshAuthoring.inspectionView(
    decoAssetState.inspection,decoAssetState.meshOptions);
  window.game1MeshAuthoring.wire(host,decoAssetState.meshOptions,null,
    Boolean(decoAssetState.inspection?.hasCollider));
}
async function decoAssetInspectSource(path){
  return request('/api/location-assets/inspect', {method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({sourcePath:path})});
}
async function decoAssetChooseModel() {
  try {
    const chosen = await request('/api/files/choose-location-asset-model', {method:'POST'});
    if (!chosen.path) return;
    // Same immediate inspect-before-registration workflow as Real Estate.
    const inspected = await decoAssetInspectSource(chosen.path);
    decoAssetState.modelPath = chosen.path;
    decoAssetState.inspection = inspected.analysis;
    decoAssetState.meshOptions = window.game1MeshAuthoring.seeded(inspected.analysis);
    $('picked-location-asset-model').textContent = inspected.sourcePath;
    if(!$('location-asset-name').value.trim()){
      $('location-asset-name').value=inspected.name.replace(/_/g,' ');
      decoAssetSyncSlug();
    }
    decoAssetRenderInspection();
  } catch (error) { toast(error.message, true); }
}
async function decoAssetChooseTexture() {
  try {
    const chosen = await window.game1AtlasWorkflow.chooseImage('/api/files/choose-location-asset-texture');
    if (!chosen.path) return;
    const match = decoAssetMatchingVariant(chosen.path);
    decoAssetState.atlasVariantId = match ? Number(match.id) : 0;
    decoAssetState.texturePath = match ? '' : chosen.path;
    $('picked-location-asset-texture').textContent = match
      ? (match.published_id
        ? `Published atlas ${match.filename} selected · changed bytes require explicit review in Edit`
        : `Registered atlas ${match.filename} selected · after registration open Publish to create Image ID`)
      : chosen.path;
    decoAssetRenderTextureReferences();
  } catch (error) { toast(error.message, true); }
}
async function decoAssetRegister() {
  try {
    const payload = {
      nameEn: $('location-asset-name').value.trim(), slug:$('location-asset-slug').value.trim(),
      category:$('location-asset-category').value, destructible: $('location-asset-destructible').checked,
      surfaceMaterial:$('location-asset-surface-material').value,
      modelSourcePath:decoAssetState.modelPath, textureSourcePath:decoAssetState.texturePath,
      atlasVariantId:decoAssetState.atlasVariantId, createOnly:true, inspectFbx:true,
      meshOptions:decoAssetState.meshOptions,
    };
    if (!payload.modelSourcePath || !decoAssetState.inspection) throw Error('Choose and analyze the FBX first');
    if (!payload.textureSourcePath && !payload.atlasVariantId) throw Error('Choose PNG/JPG or an existing atlas');
    const row = await request('/api/location-assets', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
    });
    await decoAssetLoad();
    decoAssetSetForm();
    toast(`Registered ${row.slug} · ready to publish`);
    window.game1LocationAssetWorkflow.open(row.slug, 'publish');
  } catch (error) { toast(`Register: ${error.message}`, true); }
}
async function decoAssetSaveEdits(slug, payload, expectedRevision) {
  const row = decoAssetRow(slug);
  if (!row) throw Error('Location Asset no longer exists; refresh the library');
  const saved = await request('/api/location-assets', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      slug, nameEn:payload.nameEn ?? row.name_en, category:payload.category ?? row.category,
      destructible:payload.destructible ?? Boolean(row.destructible),
      surfaceMaterial:payload.surfaceMaterial ?? row.surfaceMaterial ?? 'default',
      modelSourcePath:payload.modelSourcePath || '', textureSourcePath:payload.textureSourcePath || '',
      atlasVariantId:payload.textureSourcePath ? 0 : (payload.atlasVariantId ?? row.atlasVariantId),
      expectedRevision, editOnly:true, inspectFbx:Boolean(payload.modelSourcePath),
      ...(payload.meshOptions ? {meshOptions:payload.meshOptions} : {}),
    }),
  });
  await decoAssetLoad();
  return saved;
}
async function decoAssetPublish(slug, scope, forceModel=false) {
  if (scope !== 'model') throw Error('Location Model publication requires explicit model scope; publish Atlas via Atlas Registry');
  const row = decoAssetRow(slug);
  if (!row) throw Error('Location Asset not found');
  const imageIdBefore = String(row.texture_asset_id || '');
  const published = await request(`/api/location-assets/${encodeURIComponent(slug)}/publish-model`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({description:game1PublicationDescription('Location Asset',row.name_en),forceModel}),
  });
  if (published.resourceKind !== 'Model' || published.atlasUnchanged !== true ||
      String(published.texture_asset_id || '') !== imageIdBefore) {
    throw Error('Model publication did not confirm unchanged Atlas ID; inspect publication history before retrying');
  }
  await decoAssetLoad();
  return published;
}
// M221: one slug, ALL its managed placements; guarded in-place meshes and atlas IDs.
// Never rebuild, re-parent or move placed Models.
// Compatibility: the old direct command is intentionally disabled.
// A studio ID scan can only be followed by an explicit, token-checked Replace.
function decoAssetSyncStudio(slug) {
  return window.game1LocationAssetWorkflow.startScan(slug);
}
function decoAssetEditOpen(slug) {
  return window.game1LocationAssetWorkflow.open(slug);
}
async function decoAssetShowSyncHistory(slug) {
  const box = $('location-asset-studio-history');
  if (!box) return;
  if (!slug) { box.textContent = 'Open Edit on a Location Asset to view its history.'; return; }
  try {
    const events = [];
    let before = null;
    do {
      const cursor = before === null ? '' : `&before=${encodeURIComponent(before)}`;
      const response = await request(`/api/location-assets/studio-history?slug=${encodeURIComponent(slug)}&limit=500${cursor}`);
      events.push(...(response.events || []));
      before = response.nextCursor ?? null;
    } while (before !== null);
    box.textContent = events.length ? events.map(event => {
      const changes = (event.changes || []).map(change =>
        `${change.kind === 'model_reference' ? 'Model reference' : change.kind === 'model' ? 'Model geometry' : 'Atlas'}: ${change.oldId || 'unknown'} → ${change.newId} (${change.count})`).join('; ');
      return `${event.atUtc} · ${changes || 'No ID changes'} · pending FBX ${event.pendingGeometry}`;
    }).join('\n') : `No Studio ID changes recorded for ${slug}.`;
  } catch (error) { box.textContent = `History unavailable: ${error.message}`; }
}
async function decoAssetDelete(slug) {
  const row = decoAssetRow(slug);
  if (!row) return;
  await window.game1AssetRetirement.open({kind:'location',slug,onDone:async result => {
    await decoAssetLoad();
    if (typeof realEstateLoad === 'function') await realEstateLoad();
    window.game1LocationAssetWorkflow.close();
    toast(`Retired ${result.deleted.length} registration(s); shared atlas assets preserved`);
  }});
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
  const choice = $('location-asset-texture-reference').value;
  decoAssetState.atlasVariantId = choice.startsWith('variant:') ? Number(choice.slice(8)) : 0;
  if (decoAssetState.atlasVariantId) {
    decoAssetState.texturePath = '';
    $('picked-location-asset-texture').textContent = 'Reusing an Atlas Registry variant; no new upload';
  }
  decoAssetRenderTextureReferences();
};
$('location-asset-library-category').onchange = () => {
  const category = $('location-asset-library-category').value || 'all';
  if(category === 'all') { decoAssetState.libraryCategory = 'all'; decoAssetRemember(DECO_LIBRARY_CATEGORY_KEY, 'all'); }
  else decoAssetUseCategory(category);
  decoAssetRender();
};
$('location-asset-category').onchange = () => {
  decoAssetUseCategory($('location-asset-category').value, { updateEditor: false });
  decoAssetRender();
};
$('register-location-asset').onclick = decoAssetRegister;
$('clear-location-asset-form').onclick = decoAssetBeginNew;
