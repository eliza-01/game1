/* M474 · Character animations publication queue presentation/orchestration. */
(function(){
  const $=id=>document.getElementById(id);
  const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let api, lastFailedClip='', preparing=false;
  const queue=window.game1AnimationPublishQueueCore.create(
    async row=>{
      const result=await api.request('/api/animations/'+encodeURIComponent(row.clipId)+'/publish',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({description:$('animation-publication-description').value})
      });
      if(!/^\d+$/.test(String(result?.asset_id||''))||result.status!=='PUBLISHED')
        throw Error('publish returned without a confirmed Roblox Animation ID');
      return result;
    },render
  );
  const names={pending:'ожидает',uploading:'публикация…',published:'готово',failed:'ошибка'};
  function render(info){
    const host=$('animation-publish-queue');if(!host)return;
    if(info.total)host.hidden=false;
    $('animation-publish-queue-bar').max=Math.max(1,info.total);
    $('animation-publish-queue-bar').value=info.processed;
    $('animation-publish-queue-count').textContent=`${info.processed} / ${info.total} · успешно ${info.published}`;
    const failed=info.items.find(row=>row.status==='failed');
    const failedCount=info.items.filter(row=>row.status==='failed').length;
    const active=info.items.find(row=>row.status==='uploading');
    const pending=info.pending;
    $('animation-publish-queue-message').textContent=failed
      ?`Остановлено на ${failed.name}: ${failed.error}. Ответ Roblox мог прийти после ошибки. Не отправляй этот клип повторно без проверки публикации в Roblox.`
      :active?`Публикуется: ${active.name} · ${active.characterId}`
      :info.running?'Готовим следующую анимацию…'
      :pending?`Ожидают ${pending}. Очередь приостановлена.`
      :info.total?`Очередь завершена · опубликовано ${info.published} из ${info.total}${failedCount?' · ошибок '+failedCount:''}.`:'Нет анимаций для публикации.';
    $('animation-publish-stop').hidden=!info.running;
    $('animation-publish-continue').hidden=info.running||!pending||(!failed&&!info.stopped);
    $('animation-publish-continue').textContent=failed?'Пропустить ошибку и продолжить':'Продолжить очередь';
    $('animation-publish-all').disabled=preparing||info.running||!!api?.state()?.animationPublishing;
    const rows=$('animation-publish-queue-items');
    const scanQueue=$('animation-scan-queue-progress');
    if(scanQueue){scanQueue.hidden=!info.total;$('animation-scan-queue-bar').max=Math.max(1,info.total);$('animation-scan-queue-bar').value=info.processed;
      $('animation-scan-queue-count').textContent=`${info.processed} / ${info.total} · успешно ${info.published}`;
      $('animation-scan-queue-message').textContent=$('animation-publish-queue-message').textContent;}
    rows.innerHTML=info.items.map(row=>`<li data-status="${safe(row.status)}"><span><b>${safe(row.name)}</b><small>${safe(row.characterId)} · ${safe(row.clipId)}${row.error?' · '+safe(row.error):''}</small></span><span class="animation-queue-status">${names[row.status]}</span></li>`).join('');
  }
  async function run(items){
    if(queue.running||api.state().animationPublishing)throw Error('очередь публикации уже запущена');
    const valid=items.filter(row=>row.clipId && !row.documentOnly && !row.metadataOnly);
    if(!valid.length){api.toast('Нет неопубликованных анимаций');return {published:0,total:0,failed:'',pending:0};}
    api.state().animationPublishing=true;api.render();
    let result;
    try{result=await queue.start(valid);if(result.failed)lastFailedClip=result.failed;
      api.toast(result.failed?`Очередь остановлена: ${result.published}/${result.total}. Проверь подробности в очереди.`:`Опубликовано ${result.published} из ${result.total}`,!!result.failed);
      return result;
    }finally{api.state().animationPublishing=false;await api.load();api.render();render(queue.snapshot());}
  }
  async function publishAll(){
    if(preparing||queue.running||api.state().animationPublishing)return;
    preparing=true;render(queue.snapshot());
    try{
      const snapshot=await api.request('/api/animations/publish-queue');
      if(snapshot.publication?.configured===false)throw Error('Настрой Open Cloud перед публикацией');
      const rows=snapshot.items||[];
      if(!rows.length){api.toast('Все зарегистрированные клипы уже опубликованы (или требуют Replace)');return;}
      const unknown=rows.find(row=>row.clipId===lastFailedClip);
      if(unknown)throw Error('В очереди есть клип с неоднозначным ответом Roblox. Сначала проверь его в Roblox и обнови страницу вручную.');
      if(!confirm(`Опубликовать ${rows.length} неопубликованных анимаций Male / Female / Common последовательно? CHANGED и опубликованные не затрагиваются.`))return;
      await run(rows);
    }catch(error){api.toast(error.message,true);}
    finally{preparing=false;render(queue.snapshot());}
  }
  async function publishOne(clipId){
    if(preparing||queue.running||api.state().animationPublishing){api.toast('Дождись текущей очереди публикации',true);return;}
    if(clipId===lastFailedClip&&!confirm('Для этого клипа Roblox вернул неоднозначную ошибку. Ты проверил его публикацию в Roblox и уверен, что новая отправка не создаст дубль?'))return;
    try{return await run([{clipId,name:clipId}]);}catch(error){api.toast(error.message,true);}
  }
  async function publishRegistered(rows){
    const items=rows.filter(row=>!row.documentOnly&&!row.metadataOnly).map(row=>({clipId:row.clipId,name:row.name||row.clipId,characterId:row.characterId||''}));
    const documents=rows.length-items.length;
    if(!items.length)return {published:0,total:0,failed:'',pending:0,documents};
    const result=await run(items);
    return {...result,documents};
  }
  async function continueSkipping(){
    if(queue.running||api.state().animationPublishing)return;
    api.state().animationPublishing=true;api.render();
    try{const result=await queue.continuePending();api.toast(`Очередь: успешно ${result.published}/${result.total}${result.failed?' · остановлена на новой ошибке':''}`,!!result.failed);if(result.failed)lastFailedClip=result.failed;}
    catch(error){api.toast(error.message,true);}
    finally{api.state().animationPublishing=false;try{await api.load();}catch(error){api.toast('Не удалось обновить реестр: '+error.message,true);}api.render();render(queue.snapshot());}
  }
  function init(adapter){
    api=adapter;
    $('animation-publish-all').onclick=publishAll;
    $('animation-publish-stop').onclick=()=>queue.stop();
    $('animation-publish-continue').onclick=continueSkipping;
    render(queue.snapshot());
  }
  window.game1AnimationPublishQueue={init,publishAll,publishOne,publishRegistered,isRunning:()=>queue.running};
})();
