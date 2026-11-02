/* Character atlas presentation policy. No HTTP, Blender, model or publication logic. */
(() => {
  // Same resolution ranking as Location Assets / Real Estate (within each family).
  const colors=['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'];
  const compareVariants=(a,b)=>(Number(b.width)*Number(b.height)-Number(a.width)*Number(a.height))||
    (Number(b.width)-Number(a.width))||(Number(b.height)-Number(a.height))||(Number(a.id)-Number(b.id));
  function orderedFamilies(families){
    return [...(families||[])].sort((a,b)=>String(a.atlasKey).localeCompare(String(b.atlasKey)))
      .map(family=>({...family,variants:[...(family.variants||[])].sort(compareVariants)
        .map((variant,rank)=>({...variant,rank:Math.min(rank,4),color:colors[Math.min(rank,4)]}))}));
  }
  function matchesPart(family,partId){
    const name=String(family.atlasKey||'').toLowerCase();
    const part=String(partId||'').toLowerCase();
    // Exact family, or an explicit numbered atlas revision of this part.
    return name===part||name.startsWith(part+'_')&&/^\d{2,}$/.test(name.slice(part.length+1));
  }
  function optionsForPart(partId,families){
    const ordered=orderedFamilies(families);
    return [...ordered.filter(f=>matchesPart(f,partId)),...ordered.filter(f=>!matchesPart(f,partId))]
      .flatMap(f=>f.variants.map(v=>({...v,atlasKey:f.atlasKey,preferred:matchesPart(f,partId)})));
  }
  function variantRank(families,id){
    for(const f of orderedFamilies(families))for(const v of f.variants){
      if(String(v.id)===String(id))return v.rank;
    }
    return null;
  }
  const api={colors,orderedFamilies,optionsForPart,variantRank};
  if(typeof window!=='undefined')window.game1CharacterAtlasPresentation=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
