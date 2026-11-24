/* Armor read-only coverage and rig diagnostics. Rendering only; authoring remains
   in character-armor.js and validation in character_core/armor_readiness.py. */
(() => {
  const issues = {
    variant: 'нет варианта для этого пола',
    mesh: 'не назначен MeshPart',
    appearance: 'не назначен атлас',
    mesh_compatibility: 'MeshPart не разрешён для этого пола/слота',
    mesh_publication: 'MeshPart не опубликован или устарел',
    atlas_publication: 'атлас не опубликован или устарел',
  };
  const label = {male: 'Male', female: 'Female'};
  const description = (report, gender) => {
    const state = report?.genders?.[gender];
    if (!state) return label[gender] + ' · неизвестно';
    return `${label[gender]} ${state.assigned}/${state.required}`;
  };
  const slot = (report, key, gender) => report?.slots?.[key]?.[gender] || {ready:false,reason:'variant'};
  const badgeText = state => state.ready ? (state.source === 'unisex' ? 'Общий ✓' : 'Готов ✓') : 'Не готов · ' + (issues[state.reason] || state.reason);
  const node = (tag, value, css) => {
    const el=document.createElement(tag);
    if (value!==undefined) el.textContent=value;
    if (css) el.className=css;
    return el;
  };
  function show(set, container, choose){
    container.replaceChildren();
    if (!set?.readiness) return;
    const report=set.readiness;
    const coverage=node('div', undefined, 'armor-coverage');
    for (const gender of ['male','female']) {
      const state=report.genders[gender];
      const card=node('div', undefined,'armor-coverage-gender '+(state.complete?'armor-ready':'armor-incomplete'));
      card.append(node('strong',description(report,gender)));
      if (state.complete) card.append(node('span','Все выбранные слоты назначены.'));
      for (const missing of state.missing) {
        const b=node('button',`${missing.slot}: ${issues[missing.reason] || missing.reason}`, 'armor-coverage-link');
        b.type='button';
        b.title='Открыть слот и вариант '+label[gender];
        b.addEventListener('click',()=>choose(missing.slot,gender));
        card.append(b);
      }
      coverage.append(card);
    }
    container.append(coverage);
    const rigs=set.rigReadiness||[];
    if (rigs.length) {
      const details=node('details',undefined,'armor-rig-readiness');
      const problematic=rigs.filter(r=>!r.ready);
      details.append(node('summary', `Проверка ригов · ${rigs.length-problematic.length}/${rigs.length} готово`));
      for (const rig of rigs) {
        const block=node('div',undefined,'armor-rig-row');
        block.append(node('strong',`${rig.rigId} · ${label[rig.gender] || rig.gender} · ${rig.ready?'готов':'не готов'}`));
        if (!rig.ready) {
          for (const missing of rig.missing) {
            const slotKey=String(missing).split(':')[0];
            if (report.slots?.[slotKey]) {
              const jump=node('button',missing,'armor-coverage-link armor-rig-issue');
              jump.type='button';
              jump.addEventListener('click',()=>choose(slotKey,rig.gender));
              block.append(jump);
            } else block.append(node('div',missing,'armor-rig-issue'));
          }
        }
        details.append(block);
      }
      container.append(details);
    }
  }
  window.game1ArmorReadiness={description,slot,badgeText,show};
})();
