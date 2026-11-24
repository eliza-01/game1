'use strict';
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
const path=require('path');
class Node {
  constructor(tag){this.tag=tag;this.children=[];this.events={};this.textContent='';this.className='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  addEventListener(name,callback){this.events[name]=callback;}
  all(tag){return [...(this.tag===tag?[this]:[]),...this.children.flatMap(child=>child.all(tag))];}
}
const context={window:{},document:{createElement:tag=>new Node(tag)}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../control-center/static/armor-readiness.js'),'utf8'),context);
const ui=context.window.game1ArmorReadiness;
assert.strictEqual(ui.description({genders:{male:{assigned:2,required:4}}},'male'),'Male 2/4');
assert.strictEqual(ui.badgeText({ready:false,reason:'variant'}),'Не готов · нет варианта для этого пола');
assert.strictEqual(ui.badgeText({ready:true,source:'unisex'}),'Общий ✓');
assert.strictEqual(ui.slot({slots:{upper:{male:{ready:false,reason:'variant'}}}},'upper','male').reason,'variant');
const container=new Node('container');
const chosen=[];
ui.show({readiness:{
  genders:{male:{complete:false,assigned:1,required:2,missing:[{slot:'upper',reason:'variant'}]},
    female:{complete:true,assigned:2,required:2,missing:[]}},
  slots:{upper:{male:{ready:false,reason:'variant'},female:{ready:true}},
    boots:{male:{ready:true,source:'unisex'},female:{ready:true,source:'unisex'}}},
},rigReadiness:[
  {rigId:'human_female',gender:'female',ready:true,missing:[]},
  {rigId:'human_male',gender:'male',ready:false,missing:['boots: mesh incompatible with rig/gender']},
]},container,(slot,gender)=>chosen.push([slot,gender]));
const buttons=container.all('button');
assert.strictEqual(buttons.length,2,'one incomplete assignment and one bind-pose issue');
buttons[0].events.click();
buttons[1].events.click();
assert.deepStrictEqual(chosen,[['upper','male'],['boots','male']]);
assert.strictEqual(container.all('details').length,1);
console.log('M458 armor readiness UI: OK');
