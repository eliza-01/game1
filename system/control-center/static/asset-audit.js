// M218: read-only presentation of the M217 audit database. No Studio or asset write calls.
const assetAuditState = {events: [], nextCursor: null, loading: false, error: ''};

function assetAuditResource(event, change) {
  if (change.kind === 'atlas') return 'Atlas';
  if (change.kind === 'model_reference' || change.kind === 'model') return 'Model';
  if (event.assetType === 'image') return 'Atlas';
  if (event.assetType === 'model') return 'Model';
  if (event.assetType === 'animation') return 'Animation';
  return 'Asset';
}

function assetAuditEntries(events) {
  return events.flatMap(event => (event.changes || []).map(change => ({
    event, change, resource: assetAuditResource(event, change),
  })));
}

function assetAuditName(event) {
  // An independent shared atlas is not a model and must not masquerade as one.
  if (event.assetDomain === 'texture_atlas')
    return {label: `Shared atlas · variant ${event.assetKey}`, slug: null};
  if (event.assetDomain === 'texture_atlas_legacy')
    return {label: `Legacy atlas · ${event.assetKey}`, slug: null};
  return {label: String(event.assetKey || ''), slug: String(event.assetKey || '')};
}

function assetAuditCopyButton(value, label, kind) {
  const safe = esc(value);
  return `<button type="button" class="database-history-copy" data-copy="${safe}" title="Copy ${esc(kind)}: ${safe}">${esc(label)}</button>`;
}

function assetAuditLine({event, change, resource}) {
  const identity = assetAuditName(event);
  const name = identity.slug
    ? assetAuditCopyButton(identity.slug, identity.label, 'slug')
    : `<span class="database-history-shared">${esc(identity.label)}</span>`;
  const oldId = change.oldId
    ? assetAuditCopyButton(String(change.oldId), String(change.oldId), 'Roblox ID')
    : '<span class="database-history-unknown" title="Previous ID not recorded">—</span>';
  const newId = change.newId
    ? assetAuditCopyButton(String(change.newId), String(change.newId), 'Roblox ID')
    : '<span class="database-history-unknown">—</span>';
  const unchanged = !!change.oldId && change.oldId === change.newId;
  const syncReference = event.eventKind === 'studio_sync' && change.kind === 'model_reference';
  const notes = [event.atUtc, event.assetDomain, event.assetSlot,
    event.eventKind === 'studio_sync' ? 'Studio Sync' : event.eventKind,
    syncReference ? 'Model ID reference only · geometry unchanged' : '',
    unchanged ? 'same ID · content revision / rebind' : '',
    event.eventKind === 'studio_sync' ? `${Number(change.count || 0)} change(s)` : '',
  ].filter(Boolean).map(esc).join(' · ');
  return `<li class="database-history-row">
    <div class="database-history-main">${name}<span class="database-history-colon">:</span>
      <b class="database-history-kind">${resource}</b>${oldId}
      <span class="database-history-arrow" aria-label="replaced by">→</span>${newId}
    </div><small class="database-history-meta">${notes}</small>
  </li>`;
}

function assetAuditRender() {
  const entries = assetAuditEntries(assetAuditState.events);
  const type = $('asset-audit-type').value;
  const visible = type ? entries.filter(row => row.resource === type) : entries;
  $('asset-audit-rows').innerHTML = visible.map(assetAuditLine).join('');
  const status = $('asset-audit-status');
  status.textContent = assetAuditState.error || (assetAuditState.loading
    ? 'Loading audit history…'
    : visible.length ? '' : (assetAuditState.nextCursor !== null
      ? 'No matching entries on loaded pages. Load older events to continue.'
      : 'No retained history matches these filters.'));
  status.hidden = !status.textContent;
  $('asset-audit-count').textContent = `${visible.length} row(s) · ${assetAuditState.events.length} operation(s) loaded`;
  $('asset-audit-more').hidden = assetAuditState.nextCursor === null;
  $('asset-audit-more').disabled = assetAuditState.loading;
  $('asset-audit-refresh').disabled = assetAuditState.loading;
}

async function assetAuditLoad(reset = true) {
  if (assetAuditState.loading) return;
  if (!reset && assetAuditState.nextCursor === null) return;
  assetAuditState.loading = true;
  assetAuditState.error = '';
  if (reset) {
    assetAuditState.events = [];
    assetAuditState.nextCursor = null;
  }
  assetAuditRender();
  try {
    const domain = $('asset-audit-domain').value;
    const key = $('asset-audit-key').value.trim();
    const before = reset ? '' : `&before=${encodeURIComponent(assetAuditState.nextCursor)}`;
    const response = await request(`/api/asset-replacements?domain=${encodeURIComponent(domain)}&key=${encodeURIComponent(key)}&limit=200${before}`);
    assetAuditState.events.push(...(response.events || []));
    assetAuditState.nextCursor = response.nextCursor ?? null;
  } catch (error) {
    assetAuditState.error = `Asset history unavailable: ${error.message}`;
    toast(assetAuditState.error, true);
  } finally {
    assetAuditState.loading = false;
    assetAuditRender();
  }
}

async function assetAuditCopy(text) {
  try {
    // Explicit click only, no clipboard writes on render/navigation.
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const field = document.createElement('textarea');
      field.value = text;
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.appendChild(field);
      field.select();
      try {
        if (!document.execCommand('copy')) throw new Error('Clipboard write was rejected');
      } finally {
        field.remove();
      }
    }
    toast(`Copied: ${text}`);
  } catch (error) {
    toast(`Cannot copy to clipboard: ${error.message}`, true);
  }
}

$('asset-audit-rows').addEventListener('click', event => {
  const button = event.target.closest('button[data-copy]');
  if (!button || !$('asset-audit-rows').contains(button)) return;
  assetAuditCopy(button.dataset.copy);
});
$('asset-audit-refresh').onclick = () => assetAuditLoad(true);
$('asset-audit-more').onclick = () => assetAuditLoad(false);
$('asset-audit-domain').onchange = () => assetAuditLoad(true);
$('asset-audit-type').onchange = assetAuditRender;
$('asset-audit-key').onkeydown = event => { if (event.key === 'Enter') assetAuditLoad(true); };
window.game1AssetAuditLoad = () => assetAuditLoad(true);
