// Single publication description policy for all Game1 model assets.
// Empty selection reverts to the category default; changing selection updates the preview.
function game1PublicationDescription(category, name) {
  const base = `Game1 ${String(category || '').trim()}`.trim();
  const label = String(name || '').trim();
  return label ? `${base} ${label}` : base;
}
function game1SyncPublicationDescription(id, category, name) {
  const input = document.getElementById(id);
  if (input) input.value = game1PublicationDescription(category, name);
}

// Table-level publish actions must use the row being published, not a different
// form selection left open in the editor.
function game1DescriptionForPublishedRow(items, slug, selectedSlug, inputId, category) {
  const row = (items || []).find(item => item.slug === slug);
  const input = document.getElementById(inputId);
  if (slug === selectedSlug && input && input.value.trim()) return input.value.trim();
  return game1PublicationDescription(category, row?.name_en || slug);
}
