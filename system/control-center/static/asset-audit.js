const assetAuditState = {events: [], nextCursor: null, loading: false};

function assetAuditReplacement(event) {
  const changes = event.changes || [];
  if (!changes.length) return 'no ID change';
  return changes.map(change => {
    const oldId = change.oldId || 'none';
    const unchanged = change.oldId && change.oldId === change.newId;
    return unchanged
      ? `${esc(change.newId)} · ID retained, content revision changed`
      : `${esc(oldId)} → ${esc(change.newId)}`;
  }).join('<br>');
}

function assetAuditRender() {
  const rows = $('asset-audit-rows');
  rows.innerHTML = assetAuditState.events.length ? assetAuditState.events.map(event => {
    const instanceCount = (event.instances || []).length;
    const source = `${event.sourceSystem || ''}:${event.sourceRecord || ''}`;
    const sha = event.sourceSha256 ? `<br><small>SHA ${esc(event.sourceSha256)}</small>` : '';
    const instances = instanceCount ? `<br><small>${instanceCount} Studio instance(s)</small>` : '';
    return `<tr><td>${esc(event.atUtc)}</td><td><b>${esc(event.assetDomain)}</b><br>${esc(event.assetKey)}</td><td>${esc(event.assetType)}${event.assetSlot ? `<br><small>${esc(event.assetSlot)}</small>` : ''}</td><td>${assetAuditReplacement(event)}${instances}</td><td><small>${esc(event.eventKind)}<br>${esc(source)}</small>${sha}</td></tr>`;
  }).join('') : '<tr><td colspan="5" class="muted">No retained asset events match these filters.</td></tr>';
  $('asset-audit-count').textContent = `${assetAuditState.events.length} event(s) loaded`;
  $('asset-audit-more').hidden = assetAuditState.nextCursor === null;
}

async function assetAuditLoad(reset = true) {
  if (assetAuditState.loading) return;
  assetAuditState.loading = true;
  try {
    if (reset) {
      assetAuditState.events = [];
      assetAuditState.nextCursor = null;
    }
    const domain = $('asset-audit-domain').value;
    const key = $('asset-audit-key').value.trim();
    const before = reset || assetAuditState.nextCursor === null ? '' : `&before=${encodeURIComponent(assetAuditState.nextCursor)}`;
    const response = await request(`/api/asset-replacements?domain=${encodeURIComponent(domain)}&key=${encodeURIComponent(key)}&limit=200${before}`);
    assetAuditState.events.push(...(response.events || []));
    assetAuditState.nextCursor = response.nextCursor ?? null;
    assetAuditRender();
  } catch (error) {
    $('asset-audit-rows').innerHTML = `<tr><td colspan="5" class="muted">${esc(error.message)}</td></tr>`;
    toast(`Asset history unavailable: ${error.message}`, true);
  } finally {
    assetAuditState.loading = false;
  }
}

$('asset-audit-refresh').onclick = () => assetAuditLoad(true);
$('asset-audit-more').onclick = () => assetAuditLoad(false);
$('asset-audit-domain').onchange = () => assetAuditLoad(true);
$('asset-audit-key').onkeydown = event => { if (event.key === 'Enter') assetAuditLoad(true); };
window.game1AssetAuditLoad = () => assetAuditLoad(true);
