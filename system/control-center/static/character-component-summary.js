/* Characters catalog summary: DOM-only presentation, no registration/publication requests. */
(() => {
  const el=id=>document.getElementById('cp-'+id);
  function metric(label,value,health=''){
    const box=document.createElement('div');box.className='cp-metric'+(health?' cp-metric-'+health:'');
    const number=document.createElement('strong');number.textContent=String(value);
    const caption=document.createElement('span');caption.textContent=label;
    box.append(number,caption);return box;
  }
  function note(message,type){
    const paragraph=document.createElement('p');paragraph.className='cp-'+type;
    paragraph.textContent=message;return paragraph;
  }
  function render(catalog){
    const items=catalog?.items||[],sets=catalog?.sets||[];
    const rigs=items.filter(item=>item.kind==='rig').length;
    const published=items.filter(item=>!!item.model_asset_id&&item.published_revision===item.revision).length;
    const awaiting=items.length-published;
    el('counts').replaceChildren(
      metric('Риги',rigs),metric('Части',items.length-rigs),metric('Сеты',sets.length),
      metric('Опубликовано',`${published}/${items.length}`,items.length&&awaiting===0?'good':''),
      metric('К публикации',awaiting,awaiting?'alert':'good'));
    const hint=note('Совет: проверь FBX, зарегистрируй части и публикуй только изменённые.','advice');
    const state=awaiting
      ? note(`Внимание: ${awaiting} компонент(ов) требуют публикации. Старые Model ID сохраняются до успешной замены.`,'summary-warning')
      : note(items.length?'Готово: все компоненты опубликованы.':'Пока нет компонентов. Начни с выбора FBX.','summary-ready');
    el('flow-summary').replaceChildren(hint,state);
    el('sets').textContent=sets.length?'Сеты: '+sets.join(', '):'Сетов пока нет. Первый комплект появится при регистрации части.';
  }
  window.game1CharacterComponentSummary={render};
})();
