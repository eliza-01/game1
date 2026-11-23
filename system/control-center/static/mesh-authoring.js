/* Shared authored MeshPart/FBX presentation used by Real Estate and Location Assets.
 * The server validates physics and Blender reports; this is UI only.
 */
window.game1MeshAuthoring = (() => {
  const e = value => esc(String(value ?? ''));
  const fidelityChoices = ['Box','Hull','Default','PreciseConvexDecomposition'];
  const isRetired = name => /(?:^|_)col(?:_|$)/i.test(name);
  const isCarrier = name => String(name||'').toLowerCase()==='rig_carrier';
  const isGlass = name => String(name||'').toLowerCase().includes('glass');
  // Historical 'atlas' remains readable; new authoring uses just two modes.
  const displayAppearanceMode = mode => mode==='atlas'?'material_atlas':(mode||'');
  function atlasOptions(catalog,selected=0){
    const items=(catalog||[]).flatMap(group=>(group.variants||[]).map(v=>({...v,atlasKey:group.atlasKey})))
      .filter(v=>!v.retired||Number(v.id)===Number(selected));
    return window.game1ConsumerAtlasEditor.sections(items).map(section=>
      `<optgroup label="${e(section.label)}">`+section.items.map(v=>
        `<option value="${Number(v.id)}" ${Number(v.id)===Number(selected)?'selected':''}>`+
        `${e((window.game1AtlasFavorites?.star(v)||'')+v.atlasKey)} · ${e(v.filename)} · ${v.published_id?'Image '+e(v.published_id):'publish required'}</option>`
      ).join('')+'</optgroup>').join('');
  }
  function defaults(name,hasCollider=false,domain='estate') {
    return {glass:isGlass(name),noCollide:domain!=='location',collisionFidelity:'Box',doubleSided:false};
  }
  function effectiveFidelity(flags) {
    return fidelityChoices.includes(flags.collisionFidelity)?flags.collisionFidelity:'Box';
  }
  function normalize(name,raw,hasCollider=false,domain='estate') {
    const {collisionMesh, ...clean}={...defaults(name,hasCollider,domain),...(raw||{})};
    // texture_asset_id is derived by the server, never sent back on save.
    const {texture_asset_id,textureAssetId,...authoring}=clean;
    // An atlas-only legacy override becomes the equivalent two-mode authoring
    // record on its next explicit save; no Image ID or binding is changed here.
    if(domain==='location'&&authoring.appearanceMode==='atlas')authoring.appearanceMode='material_atlas';
    return {...authoring,collisionFidelity:effectiveFidelity(clean)};
  }
  const status=flags=>`CanCollide: ${flags.noCollide!==true} · CanTouch: false · CanQuery: ${flags.noCollide!==true}`;
  function controls(part,flags,prefix='real-estate') {
    return `<div class="real-estate-physics-controls">
      <label>Collision Fidelity <select id="${e(prefix)}-fidelity-${e(part)}" aria-label="Collision Fidelity for ${e(part)}">`+
      fidelityChoices.map(v=>`<option value="${v}" ${flags.collisionFidelity===v?'selected':''}>${v==='PreciseConvexDecomposition'?'Precise (convex decomposition)':v}</option>`).join('')+`</select></label>
      <label class="real-estate-physics-toggle"><input type="checkbox" id="${e(prefix)}-doublesided-${e(part)}" ${flags.doubleSided?'checked':''}> DoubleSided</label>
      <small class="real-estate-physics-state" id="${e(prefix)}-physics-state-${e(part)}">${status(flags)}</small>
    </div>`;
  }
  function seeded(analysis, stored={}, isNew=false) {
    const next={};
    for(const part of analysis?.meshes||[]) {
      if(isCarrier(part.name)||isRetired(part.name))continue;
      const fresh=isNew?{noCollide:true,appearanceMode:'material_atlas',visualMaterial:'Plastic',visualColor:'#FFFFFF'}:{};
      next[part.name]=normalize(part.name,{...fresh,...(stored?.[part.name]||{})},!!analysis.hasCollider,'location');
    }
    return next;
  }
  function boneList(bones,influencedBones=[],roleForName=null) {
    const influences=new Set(influencedBones||[]);
    return `<ul>${(bones||[]).map(b=>`<li><code>${e(b.name)}</code>`+
      (roleForName?`<span class="real-estate-bone-role">${e(roleForName(b.name))}</span>`:'')+
      (b.parent?` ← ${e(b.parent)}`:'')+
      (influences.has(b.name)?' · weighted':'')+`</li>`).join('')}</ul>`;
  }
  function visualControls(name,flags,ctx){
    if(!ctx)return '';
    const mode=displayAppearanceMode(flags.appearanceMode);
    const material=flags.visualMaterial||'Plastic';
    const materials=(ctx.materials||[]).map(m=>`<option value="${e(m.id)}" ${material===m.id?'selected':''}>${e(m.label)}</option>`).join('');
    const selected=Number(flags.atlasVariantId||0);
    const defaultAtlas=ctx.defaultUsesAtlas!==false;
    return `<div class="location-mesh-appearance" data-mesh-appearance>
      <label>Appearance<select data-mesh-visual="appearanceMode">
        <option value="" ${!mode?'selected':''}>Inherit Location Asset</option>
        <option value="material" ${mode==='material'?'selected':''}>Material + Color</option>
        <option value="material_atlas" ${mode==='material_atlas'?'selected':''}>Material + Color + Atlas</option>
      </select></label>
      <div data-mesh-visual-material-fields ${!mode?'hidden':''}>
        <label>Roblox Material<select data-mesh-visual="visualMaterial">${materials}</select></label>
        <label>Color<input type="color" data-mesh-visual="visualColor" value="${e(flags.visualColor||'#FFFFFF')}"></label>
      </div>
      <div data-mesh-visual-atlas-fields ${mode==='material_atlas'?'':'hidden'}>
        <label>Atlas variant<select data-mesh-visual="atlasVariantId">
          <option value="0" ${!selected?'selected':''}>${defaultAtlas?'Inherit default atlas':'Choose an atlas variant…'}</option>${atlasOptions(ctx.atlases,selected)}
        </select></label>
        <button type="button" data-mesh-new-atlas>Choose PNG/JPG for this MeshPart</button>
        <small data-mesh-atlas-path>${e(flags.textureSourcePath||'Registered atlas / inherited default')}</small>
      </div>
      <label data-mesh-visual-alpha ${mode==='material_atlas'?'':'hidden'}>
        <input type="checkbox" data-mesh-visual="alphaEnabled" ${(flags.alphaEnabled===undefined?ctx.alphaEnabled===true:flags.alphaEnabled===true)?'checked':''}> Alpha transparency
      </label>
      <small class="hint">${mode?(mode==='material_atlas'&&!selected&&!defaultAtlas?'Select a variant: the Location Asset has no default atlas.':'Independent MeshPart appearance'):'Uses the Location Asset default. Resetting an override restores inheritance.'}</small>
    </div>`;
  }
  // Native <details> keeps each FBX MeshPart's authoring controls hidden until needed.
  // Callers preserve only expanded row identities when refreshing an existing report.
  function openMeshNames(container) {
    return new Set(Array.from(container?.querySelectorAll?.('.deco-fbx-mesh[open]')||[],
      row=>row.dataset.fbxMesh));
  }
  function inspectionView(analysis,options={},prefix='location-mesh',visualContext=null,expandedMeshes=new Set()) {
    if(!analysis) return `<small class="deco-manage-value">Choose an FBX to inspect its mesh, physics and bone hierarchy.</small>`;
    const meshes=analysis.meshes||[];
    const armatures=analysis.armatures||[];
    return `<div class="deco-fbx-report" aria-label="FBX mesh inspection">
      <div class="deco-fbx-report-header"><strong>FBX · ${meshes.length} MeshPart(s)</strong><small>${armatures.length} armature(s) · dedicated COL meshes retired</small></div>

      ${meshes.filter(mesh=>!isRetired(mesh.name)).map(mesh=>{
        const name=mesh.name,flags=normalize(name,options[name],!!analysis.hasCollider,'location'),role=isCarrier(name)?'rig_carrier · shared Bone owner':isGlass(name)?'Glass':'Visual';
        const bones=mesh.bones||[];
        return `<details class="deco-fbx-mesh" data-fbx-mesh="${e(name)}" ${expandedMeshes.has(name)?'open':''}>
          <summary class="deco-fbx-mesh-title"><strong>${e(name)}</strong><small>${role} · ${Number(mesh.vertices)||0} vertices</small></summary>
          <div class="deco-fbx-mesh-body">
          ${isCarrier(name)?'<small>Authored carrier · no visual, atlas, collision or editable physics</small>':`<div class="real-estate-mesh-switches" role="group" aria-label="${e(name)} physics settings">
            <label class="real-estate-physics-toggle"><input type="checkbox" data-mesh-field="noCollide" ${flags.noCollide?'checked':''}> No Collide</label>
            <label class="real-estate-glass-toggle"><input type="checkbox" data-mesh-field="glass" ${flags.glass?'checked':''}> Glass · 0.02</label>
          </div>
          <div class="real-estate-physics-controls">
            <label>Collision Fidelity<select data-mesh-field="collisionFidelity" >
              ${fidelityChoices.map(v=>`<option value="${v}" ${v===flags.collisionFidelity?'selected':''}>${v==='PreciseConvexDecomposition'?'Precise (convex decomposition)':v}</option>`).join('')}
            </select></label>
            <label><input type="checkbox" data-mesh-field="doubleSided" ${flags.doubleSided?'checked':''}> DoubleSided</label>
            <small class="real-estate-physics-state" data-mesh-status>${status(flags)}</small>
          </div>${visualControls(name,flags,visualContext)}`}
          <details class="deco-fbx-skeleton"><summary>${e(mesh.armature||'No Armature')} · ${bones.length} bones · ${(mesh.influencedBones||[]).length} weighted</summary>
            ${bones.length?boneList(bones,mesh.influencedBones):'<small>No bones</small>'}
          </details>
          </div>
        </details>`;
      }).join('')}
      ${(analysis.unassignedArmatures||[]).length?`<small>Unassigned armatures: ${analysis.unassignedArmatures.map(e).join(', ')}</small>`:''}
    </div>`;
  }
  function wire(container,options,onChange,hasCollider=false,visualContext=null){
    container.querySelectorAll('[data-fbx-mesh]').forEach(meshRow=>{
      const name=meshRow.dataset.fbxMesh;
      if(isCarrier(name))return;
      const modeControl=meshRow.querySelector('[data-mesh-visual="appearanceMode"]');
      if(modeControl){
        const settings=()=>options[name]||normalize(name,{},hasCollider,'location');
        function changeVisual(field,value){
          const row={...settings()};
          if(field==='appearanceMode' && !value){
            delete row.appearanceMode;delete row.visualMaterial;delete row.visualColor;
            delete row.alphaEnabled;delete row.atlasVariantId;delete row.textureSourcePath;
          }else{
            row[field]=value;
            if(field==='appearanceMode' && value){
              row.visualMaterial ||= 'Plastic';row.visualColor ||= '#FFFFFF';
              if(value==='material') {delete row.atlasVariantId;delete row.textureSourcePath;delete row.alphaEnabled;}
            }
            if(field==='atlasVariantId')delete row.textureSourcePath;
          }
          options[name]=normalize(name,row,hasCollider,'location');
          const mode=options[name].appearanceMode||'';
          const material=meshRow.querySelector('[data-mesh-visual-material-fields]');
          const atlas=meshRow.querySelector('[data-mesh-visual-atlas-fields]');
          const alpha=meshRow.querySelector('[data-mesh-visual-alpha]');
          if(material)material.hidden=!mode;
          if(atlas)atlas.hidden=mode!=='material_atlas';
          if(alpha)alpha.hidden=mode!=='material_atlas';
          if(field==='atlasVariantId')meshRow.querySelector('[data-mesh-atlas-path]').textContent='Selected registered variant';
          onChange?.(options);
        }
        meshRow.querySelectorAll('[data-mesh-visual]').forEach(control=>{
          const field=control.dataset.meshVisual;
          control.onchange=()=>changeVisual(field,
            field==='alphaEnabled'?control.checked:
            field==='atlasVariantId'?Number(control.value):control.value);
        });
        const choose=meshRow.querySelector('[data-mesh-new-atlas]');
        if(choose)choose.onclick=async()=>{
          try{
            const file=await window.game1AtlasWorkflow.chooseImage('/api/files/choose-location-asset-texture');
            if(!file?.path)return;
            changeVisual('textureSourcePath',file.path);
            const row=options[name];delete row.atlasVariantId;
            meshRow.querySelector('[data-mesh-visual="atlasVariantId"]').value='0';
            meshRow.querySelector('[data-mesh-atlas-path]').textContent=file.path.split(/[\\/]/).pop()+' · publish in Atlas Registry';
          }catch(error){toast(error.message||String(error),true);}
        };
      }
      meshRow.querySelectorAll('[data-mesh-field]').forEach(control=>control.onchange=()=>{
        const field=control.dataset.meshField;
        const row=options[name]||normalize(name,{},hasCollider,'location');
        row[field]=field==='collisionFidelity'?control.value:control.checked;
        options[name]=normalize(name,row,hasCollider,'location');
        const fidelity=meshRow.querySelector('[data-mesh-field="collisionFidelity"]');
        fidelity.value=options[name].collisionFidelity;
        fidelity.disabled=false;
        meshRow.querySelector('[data-mesh-status]').textContent=status(options[name]);
        onChange?.(options);
      });
    });
  }
  return Object.freeze({defaults,effectiveFidelity,normalize,controls,seeded,openMeshNames,inspectionView,wire,status,boneList,displayAppearanceMode,atlasOptions});
})();
