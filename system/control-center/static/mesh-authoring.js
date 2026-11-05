/* Shared authored MeshPart/FBX presentation used by Real Estate and Location Assets.
 * The server validates physics and Blender reports; this is UI only.
 */
window.game1MeshAuthoring = (() => {
  const e = value => esc(String(value ?? ''));
  const fidelityChoices = ['Box','Hull','Default','PreciseConvexDecomposition'];
  const isCollider = name => /(?:^|_)col(?:_|$)/i.test(name);
  const isGlass = name => String(name||'').toLowerCase().includes('glass') && !isCollider(name);
  function defaults(name,hasCollider=false,domain='estate') {
    const lower=String(name||'').toLowerCase();
    const solidDefault=isCollider(name)||lower==='door'||lower.startsWith('door_')||isGlass(name);
    const noCollide=hasCollider ? !isCollider(name) : domain==='location'?false:!solidDefault;
    return {glass:isGlass(name),noCollide,collisionFidelity:noCollide?'Box':'PreciseConvexDecomposition',
      doubleSided:false,collisionMesh:isCollider(name)};
  }
  function effectiveFidelity(flags) {
    if (flags.noCollide !== true) return 'PreciseConvexDecomposition';
    return fidelityChoices.includes(flags.collisionFidelity)?flags.collisionFidelity:'Box';
  }
  function normalize(name,raw,hasCollider=false,domain='estate') {
    const flags={...defaults(name,hasCollider,domain),...(raw||{})};
    if (isCollider(name)) flags.glass=false;
    flags.collisionFidelity=effectiveFidelity(flags);
    return flags;
  }
  const status=flags=>`CanCollide: ${flags.noCollide!==true} · CanTouch: false · CanQuery: ${flags.noCollide!==true}`;
  function controls(part,flags,prefix='real-estate') {
    return `<div class="real-estate-physics-controls">
      <label>Collision Fidelity <select id="${e(prefix)}-fidelity-${e(part)}" aria-label="Collision Fidelity for ${e(part)}" ${flags.noCollide!==true?'disabled title="Precise is required when collision is enabled"':''}>`+
      fidelityChoices.map(v=>`<option value="${v}" ${flags.collisionFidelity===v?'selected':''}>${v==='PreciseConvexDecomposition'?'Precise (convex decomposition)':v}</option>`).join('')+`</select></label>
      <label class="real-estate-physics-toggle"><input type="checkbox" id="${e(prefix)}-doublesided-${e(part)}" ${flags.doubleSided?'checked':''}> DoubleSided</label>
      <small class="real-estate-physics-state" id="${e(prefix)}-physics-state-${e(part)}">${status(flags)}</small>
    </div>`;
  }
  function seeded(analysis, stored={}) {
    const next={};
    for(const part of analysis?.meshes||[])
      next[part.name]=normalize(part.name,stored?.[part.name],!!analysis.hasCollider,'location');
    return next;
  }
  function boneList(bones,influencedBones=[],roleForName=null) {
    const influences=new Set(influencedBones||[]);
    return `<ul>${(bones||[]).map(b=>`<li><code>${e(b.name)}</code>`+
      (roleForName?`<span class="real-estate-bone-role">${e(roleForName(b.name))}</span>`:'')+
      (b.parent?` ← ${e(b.parent)}`:'')+
      (influences.has(b.name)?' · weighted':'')+`</li>`).join('')}</ul>`;
  }
  function inspectionView(analysis,options={},prefix='location-mesh') {
    if(!analysis) return `<small class="deco-manage-value">Choose an FBX to inspect its mesh, physics and bone hierarchy.</small>`;
    const meshes=analysis.meshes||[];
    const armatures=analysis.armatures||[];
    return `<div class="deco-fbx-report" aria-label="FBX mesh inspection">
      <div class="deco-fbx-report-header"><strong>FBX · ${meshes.length} MeshPart(s)</strong><small>${armatures.length} armature(s) · ${analysis.hasCollider?'COL collision mesh detected':'No COL collider'}</small></div>
      ${!analysis.hasCollider?'<small class="real-estate-physics-caution">No dedicated COL mesh: review visual collisions before publishing.</small>':''}
      ${meshes.map(mesh=>{
        const name=mesh.name,flags=normalize(name,options[name],!!analysis.hasCollider,'location'),role=isCollider(name)?'COL · collision geometry':isGlass(name)?'Glass':'Visual';
        const bones=mesh.bones||[];
        return `<section class="deco-fbx-mesh" data-fbx-mesh="${e(name)}">
          <div class="deco-fbx-mesh-title"><strong>${e(name)}</strong><small>${role} · ${Number(mesh.vertices)||0} vertices</small></div>
          <div class="real-estate-mesh-switches" role="group" aria-label="${e(name)} physics settings">
            <label class="real-estate-physics-toggle"><input type="checkbox" data-mesh-field="noCollide" ${flags.noCollide?'checked':''}> No Collide</label>
            ${!isCollider(name)?`<label class="real-estate-glass-toggle"><input type="checkbox" data-mesh-field="glass" ${flags.glass?'checked':''}> Glass · 0.02</label>`:''}
          </div>
          <div class="real-estate-physics-controls">
            <label>Collision Fidelity<select data-mesh-field="collisionFidelity" ${flags.noCollide?'':'disabled'}>
              ${fidelityChoices.map(v=>`<option value="${v}" ${v===flags.collisionFidelity?'selected':''}>${v==='PreciseConvexDecomposition'?'Precise (convex decomposition)':v}</option>`).join('')}
            </select></label>
            <label><input type="checkbox" data-mesh-field="doubleSided" ${flags.doubleSided?'checked':''}> DoubleSided</label>
            <small class="real-estate-physics-state" data-mesh-status>${status(flags)}</small>
          </div>
          <details class="deco-fbx-skeleton"><summary>${e(mesh.armature||'No Armature')} · ${bones.length} bones · ${(mesh.influencedBones||[]).length} weighted</summary>
            ${bones.length?boneList(bones,mesh.influencedBones):'<small>No bones</small>'}
          </details>
        </section>`;
      }).join('')}
      ${(analysis.unassignedArmatures||[]).length?`<small>Unassigned armatures: ${analysis.unassignedArmatures.map(e).join(', ')}</small>`:''}
    </div>`;
  }
  function wire(container,options,onChange,hasCollider=false){
    container.querySelectorAll('[data-fbx-mesh]').forEach(meshRow=>{
      const name=meshRow.dataset.fbxMesh;
      meshRow.querySelectorAll('[data-mesh-field]').forEach(control=>control.onchange=()=>{
        const field=control.dataset.meshField;
        const row=options[name]||normalize(name,{},hasCollider,'location');
        row[field]=field==='collisionFidelity'?control.value:control.checked;
        options[name]=normalize(name,row,hasCollider,'location');
        const fidelity=meshRow.querySelector('[data-mesh-field="collisionFidelity"]');
        fidelity.value=options[name].collisionFidelity;
        fidelity.disabled=!options[name].noCollide;
        meshRow.querySelector('[data-mesh-status]').textContent=status(options[name]);
        onChange?.(options);
      });
    });
  }
  return Object.freeze({defaults,effectiveFidelity,normalize,controls,seeded,inspectionView,wire,status,boneList});
})();
