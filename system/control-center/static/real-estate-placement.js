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
  $('re-placement-refresh').disabled=state.busy;
  const items=state.data?.items||[];
  const filtered=state.house?items.filter(v=>v.houseSlug===state.house):items;
  $('re-placement-rows').innerHTML=filtered.map(item=>{
    const [x,y,z]=item.worldCFrame||[];
    const position=[x,y,z].map(v=>Number(v).toFixed(2)).join(', ');
    const rotation=(item.worldCFrame||[]).slice(3).map(v=>Number(v).toFixed(3)).join(', ');
    return `<tr><td>${String(item.plotIndex).padStart(2,'0')}</td><td><strong>${esc(item.houseSlug)}</strong></td><td>${esc(position)}<details><summary>Rotation · CFrame</summary><small>${esc(rotation)}</small></details></td><td>${Number(item.scale).toFixed(3)}</td><td>${item.revision}</td></tr>`;
  }).join('')||'<tr><td colspan="5" class="muted">No bindings for this house yet.</td></tr>';
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
    $('re-placement-status').textContent=`Bound ${house} to plot ${String(plot).padStart(2,'0')} · revision ${response.item.revision} · scale ${response.item.scale.toFixed(3)}`;
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
