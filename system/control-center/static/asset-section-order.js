/* Sidebar navigation order belongs to the browser, not to the registry or API. */
(() => {
  const KEY = 'game1.assetManager.sectionOrder.v1';
  const container = document.querySelector('.asset-sections');
  if (!container) return;
  const buttons = Array.from(container.querySelectorAll(':scope > button.asset-section'));
  const valid = new Set(buttons.map(button => button.id));
  const groups = new Map();
  for (const button of buttons) {
    const row = document.createElement('div');
    row.className = 'asset-section-row';
    row.dataset.navId = button.id;
    const handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'asset-section-grip';
    handle.draggable = true;
    handle.setAttribute('aria-label', `Reorder ${button.querySelector('b')?.textContent || button.id}`);
    handle.title = 'Drag six dots to reorder · Up/Down arrows also work';
    handle.innerHTML = '<span aria-hidden="true" class="asset-six-dots"><i></i><i></i><i></i><i></i><i></i><i></i></span>';
    button.before(row);
    row.append(handle, button);
    if (button.id === 'nav-database') {
      const submenu = document.getElementById('database-nav');
      if (submenu) row.append(submenu);
    }
    groups.set(button.id, row);
  }
  const order = () => Array.from(container.querySelectorAll(':scope > .asset-section-row'), node => node.dataset.navId);
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(order())); } catch {} };
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) || '[]');
    if (Array.isArray(stored)) {
      for (const id of [...new Set(stored)]) if (valid.has(id)) container.append(groups.get(id));
    }
  } catch {}
  let dragging = null;
  for (const [id, row] of groups) {
    const grip = row.querySelector('.asset-section-grip');
    grip.addEventListener('dragstart', event => {
      dragging = id;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', id);
      row.classList.add('dragging');
    });
    grip.addEventListener('dragend', () => {
      dragging = null;
      for (const item of groups.values()) item.classList.remove('dragging', 'drag-target');
    });
    row.addEventListener('dragover', event => {
      if (!dragging || dragging === id) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      row.classList.add('drag-target');
    });
    row.addEventListener('dragleave', () => row.classList.remove('drag-target'));
    row.addEventListener('drop', event => {
      if (!dragging || dragging === id) return;
      event.preventDefault();
      const from = groups.get(dragging);
      const after = event.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2;
      container.insertBefore(from, after ? row.nextSibling : row);
      row.classList.remove('drag-target');
      save();
    });
    grip.addEventListener('keydown', event => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      event.preventDefault();
      const sibling = event.key === 'ArrowUp' ? row.previousElementSibling : row.nextElementSibling;
      if (!sibling || !sibling.classList.contains('asset-section-row')) return;
      if (event.key === 'ArrowUp') container.insertBefore(row, sibling);
      else container.insertBefore(sibling, row);
      save();
      grip.focus();
    });
  }
})();
