// M455: read-only game Runtime localization explorer; never writes options.json.
(()=>{
  'use strict';
  const root=document.getElementById('game1-language-options');
  if(!root)return;
  const $=id=>document.getElementById(id);
  const state={catalog:null,loading:false};
  const group=$('game1-language-group');
  const locale=$('game1-language-locale');
  const search=$('game1-language-search');
  const items=$('game1-language-items');
  const status=$('game1-languages-status');
  const groupNames={language:'Language selection',action:'Interactions',hud:'HUD & feedback',weapon:'Weapons',feedback:'Common actions',actors:'NPC & monsters',items:'Equipment names'};
  const el=(tag,cls,text)=>{
    const node=document.createElement(tag);
    if(cls)node.className=cls;
    if(text!==undefined)node.textContent=String(text);
    return node;
  };
  function fillFilters(){
    group.replaceChildren(new Option('Все разделы',''));
    locale.replaceChildren(new Option('Все языки',''));
    for(const id of Object.keys(state.catalog.groups))group.add(new Option(groupNames[id]||id,id));
    for(const [id,name] of Object.entries(state.catalog.locales))locale.add(new Option(name,id));
  }
  function render(){
    if(!state.catalog)return;
    const term=search.value.trim().toLocaleLowerCase();
    const chosen=locale.value;
    const fragment=document.createDocumentFragment();
    let count=0;
    for(const [groupKey,entries] of Object.entries(state.catalog.groups)){
      if(group.value&&groupKey!==group.value)continue;
      const section=el('section','game1-language-group');
      section.append(el('h4','',groupNames[groupKey]||groupKey));
      let inGroup=0;
      for(const [key,row] of Object.entries(entries)){
        if(term&&![key,row.source,...Object.values(row.translations)].some(x=>x.toLocaleLowerCase().includes(term)))continue;
        const wrapper=el('details','game1-language-item');
        const heading=el('summary','');
        const name=el('code','',key);
        const source=el('span','',row.source);
        heading.append(name,source);
        wrapper.append(heading);
        const translations=el('div','game1-language-translations');
        for(const [id,displayName] of Object.entries(state.catalog.locales)){
          if(chosen&&chosen!==id)continue;
          const line=el('div','game1-language-translation');
          line.append(el('span','muted',displayName),el('span','',row.translations[id]));
          translations.append(line);
        }
        wrapper.append(translations);
        section.append(wrapper);
        count++;inGroup++;
      }
      if(inGroup)fragment.append(section);
    }
    items.replaceChildren(fragment);
    status.textContent=`${count} строк · ${Object.keys(state.catalog.locales).length} языков`;
  }
  async function load(){
    if(state.loading||state.catalog)return;
    state.loading=true;
    status.textContent='Загрузка…';
    try{
      const catalog=await request('/api/options/languages');
      if(catalog.schemaVersion!==1||!catalog.groups||!catalog.locales)throw Error('Incompatible localization schema');
      state.catalog=catalog;
      fillFilters();render();
    }catch(error){status.textContent=error.message||String(error);}
    finally{state.loading=false;}
  }
  root.addEventListener('toggle',()=>{if(root.open)void load();});
  group.addEventListener('change',render);
  locale.addEventListener('change',render);
  search.addEventListener('input',render);
})();
