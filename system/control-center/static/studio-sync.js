/* Shared scoped transport. Location uses separate READ-ONLY Find and guarded Replace. */
window.game1StudioSync=(()=>{
  const pending=new Set();
  const SLUG=/^[a-z0-9][a-z0-9_]{0,63}$/;
  async function send(domain,slug,body){
    if(!SLUG.test(String(slug||'')))throw Error('Studio Sync requires registered asset slug');
    if(pending.size)throw Error('Studio is processing another command');
    pending.add(slug);
    try{
      const url=domain==='location'?'/api/location-assets/studio-sync':
        `/api/real-estate/${encodeURIComponent(slug)}/sync`;
      const result=await request(url,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)});
      if(domain==='location'&&(result?.studio?.targetSlug!==slug||Number(result.studio?.replacedModels||0)!==0))
        throw Error('Studio returned an unsafe or mismatched Location Asset result');
      return result;
    }finally{pending.delete(slug);}
  }
  const scanLocation=slug=>send('location',slug,{slug,phase:'scan'});
  const replaceLocation=(slug,scanToken,selectedKeys)=>{
    if(!/^[0-9a-fA-F-]{32,36}$/.test(String(scanToken||'')))throw Error('Use Find Mesh IDs first');
    if(!Array.isArray(selectedKeys)||!selectedKeys.length||selectedKeys.length>4096||
      new Set(selectedKeys).size!==selectedKeys.length||
      selectedKeys.some(k=>!/^p[1-9][0-9]{0,3}$/.test(k)))
      throw Error('Select pending MeshParts before Sync');
    return send('location',slug,{slug,phase:'replace',scanToken,selectedKeys});
  };
  const selectLocation=(slug,scanToken,partKeys)=>{
    if(!/^[0-9a-fA-F-]{32,36}$/.test(String(scanToken||'')))throw Error('Use Find Mesh IDs first');
    if(!Array.isArray(partKeys)||!partKeys.length||partKeys.length>4096||
      new Set(partKeys).size!==partKeys.length||
      partKeys.some(key=>!/^p[1-9][0-9]{0,3}$/.test(String(key||''))))
      throw Error('Invalid scanned Models for Studio selection');
    return send('location',slug,{slug,phase:'select',scanToken,partKeys});
  };
  const attachLocation=(slug,scanToken,partKey)=>{
    if(!/^[0-9a-fA-F-]{32,36}$/.test(String(scanToken||'')))throw Error('Use Find Mesh IDs first');
    if(!/^p[1-9][0-9]{0,3}$/.test(String(partKey||'')))throw Error('Invalid historical Model row');
    return send('location',slug,{slug,phase:'attach',scanToken,partKey});
  };
  function run(domain,slug,{part=null}={}){
    if(domain==='location'){
      if(part!==null)throw Error('Location scan is scoped to the entire asset');
      return scanLocation(slug); // Old callers are never destructive.
    }
    if(domain!=='real-estate')throw Error('Unsupported Studio domain');
    if(part!==null&&(typeof part!=='string'||part.length>128||/[\x00-\x1f]/.test(part)))
      throw Error('Invalid Real Estate mesh');
    return send(domain,slug,{part:part||''});
  }
  function locationSummary(slug,studio){
    return `Studio Sync ${slug} · placed instances ${Number(studio?.matchedModels||0)}`+
      ` · atlas IDs changed ${Number(studio?.parts||0)}`+
      ` · geometry updated ${Number(studio?.geometryUpdated||0)} instance(s) / ${Number(studio?.meshPartsUpdated||0)} MeshPart(s)`+
      ` · model references changed ${Number(studio?.modelReferences||0)}`+
      '. Original placed Models and transforms retained.';
  }
  return Object.freeze({run,scanLocation,selectLocation,attachLocation,replaceLocation,locationSummary});
})();
