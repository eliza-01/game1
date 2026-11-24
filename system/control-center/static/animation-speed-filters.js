// Browser-only saved filters for Animation Speed overrides. No runtime/gameplay state.
// Pure operations are exported for regression tests; localStorage is owned by the UI.
(function(root){
  'use strict';
  const KEY='game1.animationSpeed.overrideFilters.v1';
  const MAX=12;
  function clean(value){return String(value??'').trim().replace(/\s+/g,' ').slice(0,64)}
  function canonical(value){return clean(value).toLocaleLowerCase()}
  function normalize(value){return canonical(value).replace(/[_./\\-]+/g,' ').replace(/\s+/g,' ').trim()}
  function empty(){return {saved:[],active:[]}}
  function read(raw){
    let parsed;
    try{parsed=typeof raw==='string'?JSON.parse(raw):raw}catch{return empty()}
    if(!parsed||!Array.isArray(parsed.saved))return empty();
    const saved=[];
    for(const item of parsed.saved){
      if(typeof item!=='string')continue;
      const value=clean(item);
      if(value&&!saved.some(row=>canonical(row)===canonical(value)))saved.push(value);
      if(saved.length===MAX)break;
    }
    const active=(Array.isArray(parsed.active)?parsed.active:[])
      .filter(value=>typeof value==='string')
      .map(value=>saved.find(item=>canonical(item)===canonical(value)))
      .filter((value,index,all)=>value&&all.indexOf(value)===index);
    return {saved,active};
  }
  function canAdd(state,label){
    const value=clean(label);
    return Boolean(value)&&state.saved.length<MAX&&!state.saved.some(item=>canonical(item)===canonical(value));
  }
  function add(state,label){
    if(!canAdd(state,label))return state;
    const value=clean(label);
    return {saved:[...state.saved,value],active:[...state.active,value]};
  }
  function toggle(state,label){
    const saved=state.saved.find(item=>canonical(item)===canonical(label));
    if(!saved)return state;
    const active=state.active.includes(saved)?state.active.filter(item=>item!==saved):[...state.active,saved];
    return {...state,active};
  }
  function remove(state,label){
    return {saved:state.saved.filter(item=>canonical(item)!==canonical(label)),
      active:state.active.filter(item=>canonical(item)!==canonical(label))};
  }
  function clear(state){return {...state,active:[]}}
  function matches(row,clip,query,filters){
    const parts=[row.assetId,row.stat,clip?.name,clip?.subject,clip?.kind,
      clip?.channel,clip?.clipId,clip?.scope,clip?.weaponSet,...(clip?.availableFor||[])];
    const text=parts.map(normalize).join(' ');
    const words=new Set(text.split(' '));
    return [query,...filters].every(filter=>normalize(filter).split(' ').filter(Boolean).every(token=>
      token==='male'||token==='female'?words.has(token):text.includes(token)
    ));
  }
  const api=Object.freeze({KEY,MAX,read,canAdd,add,toggle,remove,clear,matches});
  root.game1AnimationSpeedFilters=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
