/* Shared accessible dialog shell used by asset editors in multiple domains. */
window.game1AssetWorkflowDialog = (() => {
  function ensure(id, label, onClose) {
    let dialog = document.getElementById(id);
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = id;
    dialog.className = 'real-estate-mesh-dialog';
    dialog.setAttribute('aria-label', label);
    dialog.addEventListener('close', onClose);
    document.body.appendChild(dialog);
    return dialog;
  }
  // Both Real Estate and Location Assets render the same semantic tab and step
  // primitives; their domain handlers and APIs remain intentionally separate.
  function tabs(items, active, attribute = 'data-mw-tab') {
    return `<nav class="real-estate-mesh-tabs" aria-label="Resource operations">${items.map(item =>
      `<button type="button" ${attribute}="${item.id}" aria-selected="${item.id === active}">${item.label}</button>`
    ).join('')}</nav>`;
  }
  function step(title, description, content, status = '', statusClass = 'ready') {
    return `<section class="real-estate-mesh-step"><div class="real-estate-mesh-step-head">` +
      `<strong>${title}</strong>${status ? `<span class="real-estate-step-status ${statusClass}">${status}</span>` : ''}</div>` +
      `${description ? `<p>${description}</p>` : ''}${content}</section>`;
  }
  return Object.freeze({ensure, tabs, step});
})();
