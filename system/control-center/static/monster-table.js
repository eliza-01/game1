/* View-only Monster table preferences. Never reorder the canonical balance rows. */
(() => {
  const storageKey='game1.database.monsters.columns.v1';
  let preference={};
  try { preference=JSON.parse(localStorage.getItem(storageKey)||'{}')||{}; } catch (_) {}
  let sortKey=typeof preference.sortKey==='string'?preference.sortKey:null;
  let descending=preference.descending===true;
  let order=Array.isArray(preference.order)?preference.order:[];
  const collator=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
  function columns(defaults){
    order=[...new Set(order.filter(key=>defaults.includes(key))),...defaults.filter(key=>!order.includes(key))];
    if(!defaults.includes(sortKey)){sortKey=null;descending=false;}
    return [...order];
  }
  function persist(){try{localStorage.setItem(storageKey,JSON.stringify({order,sortKey,descending}));}catch(_) {}}
  function rows(source){
    if(!sortKey)return [...source];
    return [...source].sort((a,b)=>{
      const x=a[sortKey],y=b[sortKey];
      const empty=v=>v==null||v==='';
      if(empty(x)!==empty(y))return empty(x)?1:-1;
      const cmp=typeof x==='number'&&typeof y==='number'?x-y:
        typeof x==='boolean'&&typeof y==='boolean'?Number(x)-Number(y):collator.compare(String(x??''),String(y??''));
      return (descending?-cmp:cmp)||collator.compare(a.id,b.id);
    });
  }
  function move(from,to,after){
    if(from===to||!order.includes(from)||!order.includes(to))return false;
    const next=order.filter(key=>key!==from);
    next.splice(next.indexOf(to)+(after?1:0),0,from);
    order=next;persist();return true;
  }
  function decorate(header,keys,refresh){
    let dragging=null;
    const clear=()=>{for(const th of header.cells){th.classList.remove('monster-col-before','monster-col-after','monster-col-dragging');}};
    for(const [i,th] of Array.from(header.cells).entries()){
      const key=keys[i],label=th.textContent;
      th.dataset.column=key;th.textContent='';
      th.setAttribute('aria-sort',sortKey===key?(descending?'descending':'ascending'):'none');
      const wrap=document.createElement('div');wrap.className='monster-col-header';
      const grip=document.createElement('button');grip.type='button';grip.className='monster-col-grip';grip.textContent='⠿';grip.draggable=true;
      grip.title='Drag column · Alt + ←/→ to move';grip.setAttribute('aria-label',`Move ${label} column`);
      grip.addEventListener('dragstart',e=>{dragging=key;th.classList.add('monster-col-dragging');e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',key);});
      grip.addEventListener('dragend',()=>{dragging=null;clear();});
      grip.addEventListener('keydown',e=>{if(!e.altKey||!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const next=order[order.indexOf(key)+(e.key==='ArrowLeft'?-1:1)];if(next&&move(key,next,e.key==='ArrowRight')){refresh();document.querySelector(`#balance-content th[data-column="${key}"] .monster-col-grip`)?.focus();}});
      const sort=document.createElement('button');sort.type='button';sort.className='monster-col-sort';sort.textContent=label+(sortKey===key?(descending?' ↓':' ↑'):'');sort.title=`Sort by ${label}`;
      sort.addEventListener('click',()=>{descending=sortKey===key?!descending:false;sortKey=key;persist();refresh();});
      th.addEventListener('dragover',e=>{if(!dragging||dragging===key)return;e.preventDefault();e.dataTransfer.dropEffect='move';clear();const box=th.getBoundingClientRect();th.classList.add(e.clientX>box.left+box.width/2?'monster-col-after':'monster-col-before');});
      th.addEventListener('dragleave',e=>{if(!th.contains(e.relatedTarget)){th.classList.remove('monster-col-before','monster-col-after');}});
      th.addEventListener('drop',e=>{if(!dragging)return;e.preventDefault();const from=dragging;dragging=null;clear();const box=th.getBoundingClientRect();if(move(from,key,e.clientX>box.left+box.width/2))refresh();});
      wrap.append(grip,sort);th.append(wrap);
    }
  }
  window.game1MonsterTable={columns,rows,decorate};
})();
