/* M474 · sequential animation publication state machine (no browser dependencies). */
(function(root, factory){
  const api=factory();
  if(typeof module==='object' && module.exports)module.exports=api;
  else root.game1AnimationPublishQueueCore=api;
})(typeof window!=='undefined'?window:this,function(){
  function create(publish, notify=()=>{}){
    let entries=[], running=false, stopRequested=false, failure=null;
    function snapshot(){
      return {items:entries.map(item=>({...item})),running,failed:failure?.clipId||'',
        processed:entries.filter(item=>['published','failed'].includes(item.status)).length,
        published:entries.filter(item=>item.status==='published').length,
        total:entries.length,pending:entries.filter(item=>item.status==='pending').length,
        stopped:stopRequested};
    }
    function emit(){notify(snapshot());}
    function prepare(items){
      if(running)throw Error('publication queue is already running');
      const seen=new Set();
      entries=[];
      for(const raw of items){
        const clipId=String(raw.clipId||'').trim();
        if(!clipId||seen.has(clipId))continue;
        seen.add(clipId);
        entries.push({clipId,name:String(raw.name||clipId),characterId:String(raw.characterId||''),status:'pending',error:''});
      }
      failure=null;stopRequested=false;emit();
      return entries.length;
    }
    async function run(){
      if(running)throw Error('publication queue is already running');
      running=true;stopRequested=false;emit();
      try{
        for(const row of entries){
          if(stopRequested)break;
          if(row.status!=='pending')continue;
          row.status='uploading';emit();
          try{await publish({...row});row.status='published';emit();}
          catch(error){row.status='failed';row.error=String(error?.message||error);failure=row;emit();break;}
        }
      }finally{running=false;emit();}
      return snapshot();
    }
    async function start(items){prepare(items);return run();}
    async function continuePending(){
      if(running||(!failure&&!stopRequested))throw Error('no paused publication queue');
      failure=null;return run(); // Failed upload never retried automatically.
    }
    function stop(){if(running){stopRequested=true;emit();}}
    return {start,stop,continuePending,snapshot,get running(){return running}};
  }
  return {create};
});
