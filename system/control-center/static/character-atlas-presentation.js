/* Character atlas presentation policy. No HTTP, Blender, model or publication logic. */
(() => {
  // Same resolution ranking as Location Assets / Real Estate (within each family).
  const colors=['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'];
  const favored=v=>typeof window!=='undefined'&&window.game1AtlasFavorites
    ?window.game1AtlasFavorites.favorite(v):Boolean(v?.favorite);
  const compareFavorite=(a,b)=>Number(favored(b))-Number(favored(a));
  const compareVariants=(a,b)=>(Number(b.width)*Number(b.height)-Number(a.width)*Number(a.height))||
    (Number(b.width)-Number(a.width))||(Number(b.height)-Number(a.height))||(Number(a.id)-Number(b.id));
  function orderedFamilies(families){
    return [...(families||[])].sort((a,b)=>
      Number((b.variants||[]).some(favored))-Number((a.variants||[]).some(favored))||
      String(a.atlasKey).localeCompare(String(b.atlasKey)))
      .map(family=>{
        // Rank and dot color describe resolution, not the favorite ordering.
        const ranked=[...(family.variants||[])].sort(compareVariants)
          .map((variant,rank)=>({...variant,rank:Math.min(rank,4),color:colors[Math.min(rank,4)]}));
        return {...family,variants:ranked.sort((a,b)=>compareFavorite(a,b)||compareVariants(a,b))};
      });
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
      .flatMap(f=>f.variants.map(v=>({...v,atlasKey:f.atlasKey,preferred:matchesPart(f,partId)})))
      .sort((a,b)=>compareFavorite(a,b)||Number(b.preferred)-Number(a.preferred)||
        String(a.atlasKey).localeCompare(String(b.atlasKey))||compareVariants(a,b));
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
