// M479: scene / cameras / creation-panel options; no character-publishing logic.
const game1CreationViews = [
  ['SelectionOverview','01','Общая сцена'],
  ['MaleFullBody','02','Male · полный рост'],
  ['FemaleFullBody','03','Female · полный рост'],
  ['MaleFace','04','Male · лицо'],
  ['FemaleFace','05','Female · лицо']
];
const creationId = id => document.getElementById(id);
function game1CreationOptionsRender(settings){
  const value=settings||{};
  creationId('option-creation-enabled').checked=value.enabled===true;
  creationId('option-creation-use-anchors').checked=value.useStudioAnchors!==false;
  creationId('option-creation-use-markers').checked=value.useStudioSpawnMarkers!==false;
  for(const gender of ['male','female']){
    const row=value.spawnPoints?.[gender]||{};
    creationId('option-creation-spawn-'+gender+'-pos').value=(row.position||[0,0,0]).join(', ');
    creationId('option-creation-spawn-'+gender+'-rot').value=(row.rotationDegrees||[0,0,0]).join(', ');
  }
  for(const channel of ['hair','eyes','eyebrows']){
    creationId('option-creation-colors-'+channel).value=(value.colorPresets?.[channel]||[]).join(', ');
  }
  for(const channel of ['hair','eyes','eyebrows','head']){
    creationId('option-creation-materials-'+channel).value=(value.materialChoices?.[channel]||[]).join(', ');
  }
  creationId('option-creation-transition').value=String(value.transitionSeconds??0.9);
  creationId('option-creation-face-transition').value=String(value.faceTransitionSeconds??0.65);
  creationId('option-creation-width-desktop').value=String(value.desktopPanelWidthPx??460);
  creationId('option-creation-width-mobile').value=String(value.mobilePanelWidthPx??330);
  creationId('option-creation-views').innerHTML=game1CreationViews.map(([key,number,name])=>{
    const row=value.views?.[key]||{};
    return `<details class="game1-creation-view"><summary class="game1-creation-view-head"><strong>${number} · ${name}</strong><code>${key} · FOV ${row.fov??70}°</code></summary>`+
      `<div class="game1-creation-view-fields"><label>CFrame · 12 значений<input type="text" id="option-creation-cf-${key}" spellcheck="false" value="${(row.cframe||[]).join(', ')}"></label>`+
      `<label>FOV<input type="number" id="option-creation-fov-${key}" min="25" max="100" step="1" value="${row.fov??70}"></label></div></details>`;
  }).join('');
}
function game1CreationOptionsRead(){
  const number=(id,low,high,integer=false)=>{
    const raw=creationId(id).value.trim();const value=Number(raw);
    if(!raw||!Number.isFinite(value)||value<low||value>high||(integer&&!Number.isInteger(value)))
      throw Error(`${id}: expected ${low}..${high}`);
    return value;
  };
  const views={};
  for(const [key] of game1CreationViews){
    const cf=creationId('option-creation-cf-'+key).value.split(',').map(x=>x.trim());
    if(cf.length!==12||cf.some(v=>!v||!Number.isFinite(Number(v))))throw Error(`${key}: 12 CFrame values required`);
    views[key]={cframe:cf.map(Number),fov:number('option-creation-fov-'+key,25,100)};
  }
  const spawnPoints={};
  for(const gender of ['male','female']){
    const coords={};
    for(const [field,suffix] of [['position','pos'],['rotationDegrees','rot']]){
      const raw=creationId('option-creation-spawn-'+gender+'-'+suffix).value.split(',').map(x=>x.trim());
      if(raw.length!==3||raw.some(x=>!x||!Number.isFinite(Number(x))))throw Error('spawn '+gender+': expected 3 numbers');
      coords[field]=raw.map(Number);
    }
    spawnPoints[gender]=coords;
  }
  const colorPresets={};
  for(const channel of ['hair','eyes','eyebrows']){
    const colors=creationId('option-creation-colors-'+channel).value.split(',').map(x=>x.trim().toUpperCase());
    if(colors.length!==3||colors.some(x=>!/^#[0-9A-F]{6}$/.test(x)))
      throw Error('color presets '+channel+': exactly 3 #rrggbb colors required');
    colorPresets[channel]=colors;
  }
  const materialChoices={};
  const allowed=new Set(['Plastic', 'Slate', 'Fabric', 'SmoothPlastic', 'Sandstone', 'Grass', 'LeafyGrass', 'Concrete']);
  for(const channel of ['hair','eyes','eyebrows','head']){
    const materials=creationId('option-creation-materials-'+channel).value.split(',').map(x=>x.trim());
    if(!materials.length||materials.length>8||!materials.includes('Plastic')||new Set(materials).size!==materials.length||materials.some(x=>!allowed.has(x)))
      throw Error('materials '+channel+': unique valid materials with Plastic required');
    materialChoices[channel]=materials;
  }
  return {colorPresets,materialChoices,spawnPoints,useStudioSpawnMarkers:creationId('option-creation-use-markers').checked,
    enabled:creationId('option-creation-enabled').checked,
    useStudioAnchors:creationId('option-creation-use-anchors').checked,
    transitionSeconds:number('option-creation-transition',0.1,5),
    faceTransitionSeconds:number('option-creation-face-transition',0.1,5),
    desktopPanelWidthPx:number('option-creation-width-desktop',240,540,true),
    mobilePanelWidthPx:number('option-creation-width-mobile',240,540,true),views};
}
creationId('option-creation-save').onclick=()=>{
  try{game1OptionsSave({characterCreation:game1CreationOptionsRead()},
    'Character Creation saved · Rojo Sync / new Play');}
  catch(error){toast(error.message||String(error),true)}
};
