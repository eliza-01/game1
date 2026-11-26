/* M538 · Read-only projection of the Design Markdown topology table. */
(() => {
  const headers=['Территория','LVL','Колонка','Ряд','Дорога далее','Обратный путь'];
  const palette=['#83ad61','#9b85c4','#c4a16f','#45b6a0','#c77659','#789bd4'];
  const isMapHeader=values=>values.length===headers.length&&headers.every((v,i)=>v===values[i]);
  function parse(rows){
    if(!Array.isArray(rows)||rows.length<2||rows.length>8)return null;
    const used=new Set(),ranges=new Set();const nodes=[];
    for(const [i,values] of rows.entries()){
      if(values.length!==headers.length)return null;
      const [name,range,column,row,next,back]=values;
      if(!name||name.length>24||!/^\d{1,2}–\d{1,2}$/.test(range)||! /^[12]$/.test(column)||! /^[1-4]$/.test(row)||next.length>24)return null;
      const [low,high]=range.split('–').map(Number),key=column+':'+row;
      if(low<1||low>high||used.has(key)||ranges.has(range)||(i&&low!==nodes[i-1].high+1))return null;
      used.add(key);ranges.add(range);nodes.push({name,range,high,x:160+(Number(column)-1)*320,y:55+(Number(row)-1)*105,next,back,color:palette[i%palette.length]});
    }
    for(const [i,n] of nodes.entries()){
      const later=nodes[i+1],returnNode=nodes.find(v=>v.range===n.back);
      if((later&&(!n.next||n.next==='—'||(Math.abs(later.x-n.x)+Math.abs(later.y-n.y)!==105&&Math.abs(later.x-n.x)+Math.abs(later.y-n.y)!==320)))||(!later&&n.next!=='—'))return null;
      if(n.back!=='—'&&(!returnNode||returnNode===n||(Math.abs(returnNode.x-n.x)+Math.abs(returnNode.y-n.y)!==105&&Math.abs(returnNode.x-n.x)+Math.abs(returnNode.y-n.y)!==320)))return null;
    }
    return nodes;
  }
  function render(rows,onSelect){
    const nodes=parse(rows);if(!nodes)return null;
    const host=document.createElement('div');host.className='kb-map';
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 640 435');svg.setAttribute('aria-label','Маршрут первого релиза');host.append(svg);
    const el=(tag,attrs,parent=svg,text)=>{const e=document.createElementNS(svg.namespaceURI,tag);for(const [key,value] of Object.entries(attrs))e.setAttribute(key,String(value));if(text!==undefined)e.textContent=text;parent.append(e);return e};
    function edge(a,b,label,back=false){
      const dx=Math.sign(b.x-a.x),dy=Math.sign(b.y-a.y);
      const x1=a.x+dx*108,y1=a.y+dy*37,x2=b.x-dx*110,y2=b.y-dy*39;
      const group=el('g',{class:back?'kb-map-return':'kb-map-route','aria-hidden':'true'});
      el('path',{d:`M${x1} ${y1} L${x2} ${y2}`,fill:'none'},group);
      el('polygon',{points:`${x2},${y2} ${x2-dx*10-dy*5},${y2-dy*10-dx*5} ${x2-dx*10+dy*5},${y2-dy*10+dx*5}`},group);
      el('text',{x:(x1+x2)/2+(dy?10:0),y:(y1+y2)/2+(dx?-10:4),'text-anchor':dy?'start':'middle'},group,label);
    }
    nodes.forEach((n,i)=>{if(i+1<nodes.length)edge(n,nodes[i+1],n.next);if(n.back!=='—')edge(n,nodes.find(v=>v.range===n.back),'возврат',true)});
    nodes.forEach((n,i)=>{
      const g=el('g',{class:'kb-map-zone',role:'button',tabindex:0,'aria-label':`${n.name}, уровень ${n.range}`,'data-range':n.range});g.style.setProperty('--zone-color',n.color);
      el('rect',{x:n.x-108,y:n.y-37,width:216,height:74,rx:12},g);
      el('text',{x:n.x,y:n.y-4,'text-anchor':'middle',class:'kb-map-name','font-size':n.name.length>17?'15':'17'},g,n.name);
      el('text',{x:n.x,y:n.y+20,'text-anchor':'middle',class:'kb-map-level'},g,`LVL ${n.range}${i===0?' · старт':''}`);
      g.addEventListener('click',()=>onSelect(n.range));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(n.range)}});
    });
    const legend=document.createElement('div');legend.className='kb-map-legend';
    for(const [css,label] of [['main','Основной путь'],['return','Обратный путь'],['hint','Нажми на зону → цели по уровням']]){const span=document.createElement('span');span.className='kb-map-key-'+css;span.textContent=label;legend.append(span)}host.append(legend);
    return host;
  }
  function colorSections(host){
    const colors=new Map(Array.from(host.querySelectorAll('.kb-map-zone'),node=>[node.getAttribute('data-range'),node.style.getPropertyValue('--zone-color')]));
    for(const zone of host.querySelectorAll('[data-zone-range]')){const color=colors.get(zone.dataset.zoneRange);if(color)zone.style.setProperty('--zone-color',color)}
  }
  window.game1KanbanDesignMap={isMapHeader,parse,render,colorSections};
})();
