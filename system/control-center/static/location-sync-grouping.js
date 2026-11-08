/* Pure Location Studio report presentation: MeshParts sharing one verified
 * placement identity render as one Model card. No Studio or network writes. */
window.game1LocationSyncGrouping=Object.freeze({
  models(parts){
    if(!Array.isArray(parts))return [];
    const grouped=[],byModel=new Map();
    for(const part of parts){
      const identity=part?.managed&&part.instanceId
        ?`managed:${part.instanceId}`:`model:${part?.modelPath||part?.path||''}`;
      let model=byModel.get(identity);
      if(!model){
        model={identity,parts:[],managed:Boolean(part?.managed),
          modelName:part?.modelName||part?.name||'',modelPath:part?.modelPath||part?.path||''};
        grouped.push(model);byModel.set(identity,model);
      }
      model.parts.push(part);
    }
    return grouped;
  },
});
