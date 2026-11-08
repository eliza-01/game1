'use strict';
const assert=require('assert');
global.window=global;
require('../control-center/static/location-sync-grouping.js');

const parts=[];
for(let model=1;model<=4;model++){
  const instanceId=`tree-${model}`;
  const modelPath=`Workspace.Plots.0${model}.christmas_tree__${model}`;
  parts.push({key:`v${model}`,managed:true,instanceId,modelPath,name:'christmas_tree',isCollider:false});
  parts.push({key:`c${model}`,managed:true,instanceId,modelPath,name:'col_mesh',isCollider:true});
}
const grouped=game1LocationSyncGrouping.models(parts);
assert.equal(grouped.length,4,'eight MeshParts must render as four placed Models');
assert.deepEqual(grouped.map(model=>model.parts.length),[2,2,2,2]);
assert(grouped.every(model=>model.managed));
assert.equal(game1LocationSyncGrouping.models(null).length,0);
console.log('M262 legacy rig grouping: OK');
