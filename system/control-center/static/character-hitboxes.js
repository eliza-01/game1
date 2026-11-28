/* Explicit offline authoring. No publishing or runtime commands. */
(() => {
  const button=document.getElementById('character-hitboxes-capture');
  const status=document.getElementById('character-hitboxes-status');
  if(!button||!status)return;
  button.addEventListener('click',async()=>{
    button.disabled=true;
    const messages=[];
    try{
      const catalog=await request('/api/characters/assemblies',{cache:'no-store'});
      // Same published assembly list as the Character editor.
      const rows=(catalog.items||[]).filter(row=>row.assembly_resolved?.ready===true);
      if(!rows.length)throw Error('No published Character assemblies');
      for(const row of rows){
        status.textContent=`${row.id} · capturing components… ${messages.join(' · ')}`;
        try{
          const result=await request('/api/characters/hitboxes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:row.id})});
          messages.push(`${row.id}: ${result.components} components / ${result.variants} assemblies`);
        }catch(error){messages.push(`${row.id}: ERROR ${error.message}`);}
      }
      status.textContent=messages.join(' · ')+' · Runtime coverage not verified.';
    }catch(error){status.textContent=error.message;}
    finally{button.disabled=false;}
  });
})();
