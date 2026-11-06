/* M249 Location category picker: presentation only. The native select remains
 * the form value and is still the sole writer read by registration/edit APIs. */
window.game1LocationCategoryPicker = (() => {
  const escape = (value) => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  function mount(select, options) {
    if (!select || !options?.categoryGroups?.length) return;
    if (select.parentElement?.classList.contains('la-category-control')) {
      refresh(select); return;
    }
    const wrap = document.createElement('span');
    wrap.className = 'la-category-control';
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add('la-category-native');
    select.tabIndex = -1;
    const trigger = document.createElement('button');
    trigger.className = 'la-category-trigger'; trigger.type = 'button';
    trigger.setAttribute('aria-haspopup','dialog');
    trigger.setAttribute('aria-expanded','false');
    const popup = document.createElement('div');
    popup.className = 'la-category-popup';
    popup.setAttribute('role','dialog');
    popup.setAttribute('aria-label','Location Asset categories');
    popup.hidden = true;
    popup.setAttribute('popover','manual');
    popup.innerHTML = options.categoryGroups.map(group =>
      `<div class="la-category-column"><strong>${escape(group.label)}</strong>` +
      group.categories.map(item => `<button type="button" data-category="${escape(item.id)}">${escape(item.label)}</button>`).join('')+
      '</div>').join('');
    if ([...select.options].some(option=>option.value==='all')) {
      popup.querySelector('.la-category-column')?.insertAdjacentHTML('afterbegin',
        '<button type="button" data-category="all">All categories</button>');
    }
    wrap.appendChild(trigger); wrap.appendChild(popup);
    let removeOutside = null;
    const close=()=>{
      if(popup.matches(':popover-open'))popup.hidePopover();
      popup.hidden=true;
      trigger.setAttribute('aria-expanded','false');
      if(removeOutside){document.removeEventListener('pointerdown',removeOutside,true);removeOutside=null;}
    };
    trigger.onclick=()=>{
      if(!popup.hidden){close();return;}
      document.querySelectorAll('.la-category-popup:not([hidden])').forEach(other=>{if(other.matches(':popover-open'))other.hidePopover();other.hidden=true;other.parentElement?.querySelector('.la-category-trigger')?.setAttribute('aria-expanded','false');});
      popup.hidden=false;
      const rect=trigger.getBoundingClientRect();
      popup.style.left=Math.max(12,Math.min(rect.left,window.innerWidth-420))+'px';
      popup.style.top=Math.min(rect.bottom+6,window.innerHeight-90)+'px';
      if(typeof popup.showPopover==='function')popup.showPopover();
      trigger.setAttribute('aria-expanded','true');
      refresh(select);
      removeOutside=(event)=>{if(!wrap.contains(event.target))close();};
      document.addEventListener('pointerdown',removeOutside,true);
    };
    popup.addEventListener('click',event=>{
      const button=event.target.closest('button[data-category]');
      if(!button)return;
      select.value=button.dataset.category;
      select.dispatchEvent(new Event('change',{bubbles:true}));
      refresh(select);close();trigger.focus();
    });
    popup.addEventListener('keydown',event=>{if(event.key==='Escape'){close();trigger.focus();}});
    trigger.addEventListener('keydown',event=>{if(event.key==='Escape')close();});
    refresh(select);
  }
  function refresh(select) {
    const wrap=select?.parentElement;
    if(!wrap?.classList.contains('la-category-control'))return;
    const selected=select.selectedOptions[0];
    wrap.querySelector('.la-category-trigger').textContent=(selected?.textContent||'Choose category')+' ▾';
    wrap.querySelectorAll('[data-category]').forEach(button=>{
      const current=button.dataset.category===select.value;
      button.classList.toggle('active',current);
      button.setAttribute('aria-pressed',String(current));
    });
  }
  return Object.freeze({mount,refresh});
})();
