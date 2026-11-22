/* Create-only display names shared by Game1 registrars. Slugs remain independent. */
window.game1AssetNameDefaults = (() => {
  function title(value) {
    return String(value ?? '').trim().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')
      .replace(/[^\s]+/gu, word => word.charAt(0).toLocaleUpperCase() + word.slice(1).toLocaleLowerCase());
  }
  function fromPath(path) {
    return title(String(path ?? '').split(/[\\/]/).pop().replace(/\.fbx$/i, ''));
  }
  function fillFromPath(field, path, onFill, isNew) {
    if (!isNew || !field || field.value.trim()) return false;
    const display = fromPath(path);
    if (!display) return false;
    field.value = display;
    onFill?.();
    return true;
  }
  return Object.freeze({title, fromPath, fillFromPath});
})();
