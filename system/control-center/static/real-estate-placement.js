/* Real Estate placement authoring UI — does not own house/asset rendering. */
const realEstatePlacementState = {data:null, busy:false, house:'', plot:1};
const RE_PLACEMENT_KEY = 'game1.realEstate.placement';
function game1RealEstatePlacementRender(){
  const state=realEstatePlacementState;
  const houses=realEstateRows().map(row=>row.slug).sort();
  const house=$('re-placement-house');
  if(!house)return;
  if(!state.house){
    try{const saved=JSON.parse(localStorage.getItem(RE_PLACEMENT_KEY)||'{}');
      state.house=saved.house||'';state.plot=Number(saved.plot)||1;}catch{}
  }
  if(!houses.includes(state.house))state.house='';
  house.innerHTML='<option value="">Choose registered house</option>'+houses.map(slug=>
    `<option value="${esc(slug)}" ${slug===state.house?'selected':''}>${esc(slug)}</option>`).join('');
  const plot=$('re-placement-plot');
  plot.innerHTML=Array.from({length:50},(_,i)=>`<option value="${i+1}" ${i+1===state.plot?'selected':''}>Plot ${String(i+1).padStart(2,'0')}</option>`).join('');
  house.disabled=state.busy;plot.disabled=state.busy;
  $('re-placement-bind').disabled=state.busy||!state.house;
  $('re-placement-prev').disabled=state.busy;
  $('re-placement-next').disabled=state.busy;
  $('re-placement-refresh').disabled=state.busy;
  const all=state.data?.items||[];
  const allAnchored=all.length>0&&all.every(item=>item.anchored!==false);
  const header=$('re-placement-toggle-all');
  header.textContent=allAnchored?'≋':'⚓';
  header.title=allAnchored?'Free all bindings':'Anchor all bindings';
  header.disabled=state.busy||!all.length;
  $('re-placement-anchor-all').disabled=state.busy||!all.length;
  $('re-placement-free-all').disabled=state.busy||!all.length;
  const selectedBindings=state.house?all.filter(item=>item.houseSlug===state.house):[];
  $('re-placement-place-all').disabled=state.busy||!selectedBindings.length||selectedBindings.some(item=>!Array.isArray(item.houseAnchorLocalCFrame));
  $('re-placement-clear-all').disabled=state.busy;
  const items=state.data?.items||[];
  const filtered=state.house?items.filter(v=>v.houseSlug===state.house):items;
  $('re-placement-rows').innerHTML=filtered.map(item=>{
    const [x,y,z]=item.worldCFrame||[];
    const position=[x,y,z].map(v=>Number(v).toFixed(2)).join(', ');
    const rotation=(item.worldCFrame||[]).slice(3).map(v=>Number(v).toFixed(3)).join(', ');
    const rotationReady=Array.isArray(item.houseAnchorLocalCFrame)&&item.houseAnchorLocalCFrame.length===12;
    const anchored=item.anchored!==false;
    const symbol=anchored?'⚓':'≋';
    const label=anchored?'Free this house':'Anchor this house';
    return `<tr><td><button type="button" class="re-anchor-toggle ${anchored?'is-anchored':'is-free'}" data-placement-anchor="${anchored?'free':'anchor'}" data-house="${esc(item.houseSlug)}" data-plot="${item.plotIndex}" title="${label}" aria-label="${label}" ${state.busy?'disabled':''}>${symbol}</button></td><td><div class="re-placement-row-actions"><button type="button" data-placement-action="place" data-house="${esc(item.houseSlug)}" data-plot="${item.plotIndex}" title="${rotationReady?'Place saved house':'Re-Bind this house to capture rotation'}" ${state.busy||!rotationReady?'disabled':''}>Place</button><button type="button" data-placement-action="clear" data-house="${esc(item.houseSlug)}" data-plot="${item.plotIndex}" ${state.busy?'disabled':''}>Clear</button></div></td><td>${String(item.plotIndex).padStart(2,'0')}</td><td><strong>${esc(item.houseSlug)}</strong>${rotationReady?'':'<small class="muted"> · Re-Bind for rotation</small>'}</td><td>${esc(position)}<details><summary>Rotation · CFrame</summary><small>${esc(rotation)}</small></details></td><td>${Number(item.scale).toFixed(3)}</td><td>${item.revision}</td></tr>`;
  }).join('')||'<tr><td colspan="7" class="muted">No bindings for this house yet.</td></tr>';
}
function realEstatePlacementRemember(){
  try{localStorage.setItem(RE_PLACEMENT_KEY,JSON.stringify({house:realEstatePlacementState.house,plot:realEstatePlacementState.plot}));}catch{}
}
async function game1RealEstatePlacementLoad(){
  try{
    realEstatePlacementState.data=await request('/api/real-estate/placements');
    game1RealEstatePlacementRender();
  }catch(error){$('re-placement-status').textContent='Placement loading failed: '+error.message;}
}
async function realEstatePlacementBind(){
  const s=realEstatePlacementState;
  if(!s.house||s.busy)return;
  const house=s.house,plot=s.plot;
  s.busy=true;game1RealEstatePlacementRender();
  $('re-placement-status').textContent=`Reading ${house} on plot ${String(plot).padStart(2,'0')} from Studio selection…`;
  try{
    const response=await request('/api/real-estate/placements/bind',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({houseSlug:house,plotIndex:plot}),
    });
    $('re-placement-status').textContent=`Bound ${house} to plot ${String(plot).padStart(2,'0')} · revision ${response.item.revision} · scale ${response.item.scale.toFixed(3)} · house pivot and rotation captured`;
    await game1RealEstatePlacementLoad();
  }catch(error){
    $('re-placement-status').textContent='Bind failed: '+error.message;
    toast(error.message,true);
  }finally{s.busy=false;game1RealEstatePlacementRender();}
}
$('re-placement-house').onchange=e=>{realEstatePlacementState.house=e.target.value;realEstatePlacementRemember();game1RealEstatePlacementRender();};
$('re-placement-plot').onchange=e=>{realEstatePlacementState.plot=Number(e.target.value);realEstatePlacementRemember();game1RealEstatePlacementRender();};
$('re-placement-bind').onclick=realEstatePlacementBind;
$('re-placement-refresh').onclick=game1RealEstatePlacementLoad;

function realEstatePlacementShift(delta){
  const state=realEstatePlacementState;
  if(state.busy)return;
  state.plot=((state.plot-1+delta+50)%50)+1;
  realEstatePlacementRemember();game1RealEstatePlacementRender();
}
$('re-placement-prev').onclick=()=>realEstatePlacementShift(-1);
$('re-placement-next').onclick=()=>realEstatePlacementShift(1);
$('re-placement-rows').addEventListener('click',async event=>{
  const button=event.target.closest('[data-placement-action]');
  if(!button || realEstatePlacementState.busy)return;
  const house=button.dataset.house,plot=Number(button.dataset.plot),action=button.dataset.placementAction;
  if(!house||!Number.isInteger(plot)||plot<1||plot>50||!['place','clear'].includes(action))return;
  const state=realEstatePlacementState;
  state.busy=true;game1RealEstatePlacementRender();
  $('re-placement-status').textContent=`${action} ${house} on plot ${String(plot).padStart(2,'0')}…`;
  try{
    const result=await request('/api/real-estate/placements/preview',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({houseSlug:house,plotIndex:plot,action}),
    });
    const verified=action==='place' ? ` · ${result.studio.anchored?'Anchored':'Free'} · ${result.studio.anchoredPartsVerified} BaseParts verified` : '';
    $('re-placement-status').textContent=`Plot ${String(plot).padStart(2,'0')} · ${house} · ${result.studio?.status||action}${verified}. Studio Undo is available.`;
  }catch(error){
    $('re-placement-status').textContent=`${action} failed: ${error.message}`;
    toast(error.message,true);
  }finally{state.busy=false;game1RealEstatePlacementRender();}
});

async function game1PlacementSetAnchored(scope, anchored, house, plot){
  const state=realEstatePlacementState;
  if(state.busy)return;
  state.busy=true;game1RealEstatePlacementRender();
  $('re-placement-status').textContent=(anchored?'Anchoring':'Freeing')+(scope==='all'?' all bound houses':` ${house} on plot ${plot}`)+' in Studio…';
  try{
    const payload={scope,anchored};
    if(scope==='one'){payload.houseSlug=house;payload.plotIndex=plot;}
    const response=await request('/api/real-estate/placements/anchors',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),
    });
    $('re-placement-status').textContent=`${anchored?'Anchored':'Freed'} · ${response.changed} binding(s) updated · ${response.studio?.changed||0} placed preview(s) in Studio. Undo is available.`;
    await game1RealEstatePlacementLoad();
  }catch(error){
    $('re-placement-status').textContent='Anchor/Free failed: '+error.message;
    toast(error.message,true);
  }finally{state.busy=false;game1RealEstatePlacementRender();}
}
$('re-placement-rows').addEventListener('click',event=>{
  const button=event.target.closest('[data-placement-anchor]');
  if(!button)return;
  game1PlacementSetAnchored('one',button.dataset.placementAnchor==='anchor',button.dataset.house,Number(button.dataset.plot));
});
function game1PlacementToggleAll(){
  const items=realEstatePlacementState.data?.items||[];
  if(!items.length)return;
  game1PlacementSetAnchored('all',!items.every(item=>item.anchored!==false));
}
$('re-placement-toggle-all').onclick=game1PlacementToggleAll;
$('re-placement-anchor-all').onclick=()=>game1PlacementSetAnchored('all',true);
$('re-placement-free-all').onclick=()=>game1PlacementSetAnchored('all',false);

// Bulk preview shares the saved bindings and Studio placement transaction with
// the per-row Place/Clear actions. Never send coordinates from the browser.
async function game1PlacementBulk(action){
  const state=realEstatePlacementState;
  if(state.busy)return;
  if(action==='place_all'&&!state.house)return;
  const house=state.house;
  state.busy=true;game1RealEstatePlacementRender();
  $('re-placement-status').textContent=action==='place_all'
    ?`Placing ${house} on every bound plot in Studio…`
    :'Clearing all managed house previews in Studio…';
  try{
    const response=await request('/api/real-estate/placements/bulk',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(action==='place_all'?{action,houseSlug:house}:{action}),
    });
    const studio=response.studio;
    const verified=action==='place_all'?` · ${studio.anchoredPartsVerified} BaseParts verified`:'';
    $('re-placement-status').textContent=`${action==='place_all'?'Placed':'Cleared'} ${studio.changed} managed house(s)${verified}. One Studio Undo is available.`;
  }catch(error){
    $('re-placement-status').textContent=`${action==='place_all'?'Place all':'Clear all'} failed: ${error.message}`;
    toast(error.message,true);
  }finally{state.busy=false;game1RealEstatePlacementRender();}
}
$('re-placement-place-all').onclick=()=>game1PlacementBulk('place_all');
$('re-placement-clear-all').onclick=()=>game1PlacementBulk('clear_all');
