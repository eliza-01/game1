/* Atlas presentation identity. Publication and reuse references remain untouched.
 * <name>_<variant>_<W>x<H>_atlas.png -> name / variant / resolution.
 * Older image names are displayed by their filename stem, never by model owner.
 */
(() => {
  const filenameOf=value=>String(value||'').split(/[\\/]/).pop();
  function describe({filename='',atlasKey='',resolution=''}={}){
    const file=filenameOf(filename);
    const canonical=/^(.+)_([1-9]\d*)x([1-9]\d*)_atlas\.(png|jpe?g|webp)$/i.exec(file);
    const stem=file.replace(/\.[^.]+$/, '');
    const key=String(atlasKey||canonical?.[1]||stem.replace(/_atlas$/i,'')||'unknown atlas').trim();
    const match=/^(.+)_([0-9]{2,})$/.exec(key);
    return {key,name:match?.[1]||key,variant:match?.[2]||'',
      resolution:resolution||(canonical?`${canonical[2]}×${canonical[3]}`:''),filename:file};
  }
  function pixelArea(value){
    const match=/^(\d+)×(\d+)$/.exec(String(value||''));
    return match?Number(match[1])*Number(match[2]):0;
  }
  function label(value,{assetId='',includeFilename=false}={}){
    const item=describe(value);
    return [item.key,item.resolution,includeFilename?item.filename:'',String(assetId||'')].filter(Boolean).join(' · ');
  }
  const api={describe,label,pixelArea};
  if(typeof window!=='undefined')window.game1AtlasIdentity=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
