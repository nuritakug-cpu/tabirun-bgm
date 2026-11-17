/* TOP RUN PORTAL - Android/desktop notification receiver.
   One existing-origin, narrowly-scoped Service Worker; no Firebase or secrets.
   Installed ONLY from TOP_RUN_PORTAL Stage3 notification settings, after identity eligibility.
   v452: PORTALで既読になったとき、この受け口自身が出した通知とバッジを消す（message 'tr-clear-v452'）。
   v456: 原因の確認用に、受け取った通知・消した通知の記録（直近20件）をスマホの中（Cache Storage）にだけ残す。
         PORTAL の「アイコンの点（バッジ）を消す」で表示する。通知の出し方・タップの動きは変えない。外へは送らない。 */
'use strict';
const PORTAL='https://nuritakug-cpu.github.io/tabirun-bgm/TOP_RUN_PORTAL.html';
const PORTAL_URL=new URL(PORTAL);

// ---- v456: 記録（スマホの中だけ）
const LOG_CACHE='tr-push-log-v456';
const LOG_KEY='./__tr_push_log_v456__';
async function addLog(entry){
  try{
    const cache=await caches.open(LOG_CACHE);
    let list=[];
    try{const r=await cache.match(LOG_KEY);if(r)list=await r.json();}catch{list=[];}
    if(!Array.isArray(list))list=[];
    list.push(Object.assign({at:Date.now()},entry));
    list=list.slice(-20);
    await cache.put(LOG_KEY,new Response(JSON.stringify(list),{headers:{'Content-Type':'application/json'}}));
  }catch{/* 記録できなくても通知の動きは止めない */}
}
async function countShown(){
  try{return (await self.registration.getNotifications()).length;}catch{return -1;}
}

function allowedPage(raw){
  try{
    const url=new URL(typeof raw==='string'?raw:PORTAL,PORTAL);
    if(url.origin!==PORTAL_URL.origin||url.pathname!==PORTAL_URL.pathname)return PORTAL;
    const target=url.searchParams.get('pushTo');
    return target==='chat'||target==='notices'?PORTAL+'?pushTo='+target:PORTAL;
  }catch{return PORTAL;}
}

self.addEventListener('install',()=>{self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim());});

self.addEventListener('push',event=>{
  event.waitUntil((async()=>{
    let value={},parsed='ok';
    try{value=event.data?.json()||{};if(!event.data)parsed='empty';}catch{parsed='invalid';/* Invalid payload: use generic notification. */}
    const n=value?.notification&&typeof value.notification==='object'?value.notification:value;
    const title=typeof n?.title==='string'?n.title.slice(0,80):'TOP RUN';
    const body=typeof n?.body==='string'?n.body.slice(0,220):'新しい通知があります。';
    const navigate=allowedPage(n?.navigate);
    const tag=typeof n?.tag==='string'?n.tag.slice(0,70):'top-run-message';
    let shown='ok';
    try{
      await self.registration.showNotification(title,{
        body,lang:'ja',dir:'auto',tag,
        data:{url:navigate},silent:n?.silent===true
      });
    }catch(e){shown='error:'+String(e?.name||e?.message||'').slice(0,40);}
    const badge=Number.isSafeInteger(value?.badge)&&value.badge>=0?value.badge:1;
    let badgeApi=typeof self.navigator?.setAppBadge==='function'?'あり':'なし';
    try{if(badge===0){await self.navigator?.clearAppBadge?.();}else{await self.navigator?.setAppBadge?.(badge);}}catch{badgeApi='エラー';}
    const after=await countShown();
    // 題名と本文の長さだけを残す（本文そのものは残さない）
    await addLog({ev:'受信',title:title.slice(0,30),bodyLen:body.length,tag,parsed,shown,badge,badgeApi,after,
      hasBody:typeof n?.body==='string',silent:n?.silent===true});
    // 少しあとにも数える（出した直後に誰かが消していないか）
    await new Promise(r=>setTimeout(r,3000));
    const later=await countShown();
    if(later!==after)await addLog({ev:'3秒後',after:later});
  })());
});

// v452: PORTALの既読に合わせて、この受け口が出した通知とバッジを消す。
const isChatV452=n=>/chat|room|チャット|ルーム/.test([n.tag,n.title,n.body,JSON.stringify(n.data||{})].join(' ').toLowerCase());
self.addEventListener('message',event=>{
  const d=event.data;
  if(!d||d.type!=='tr-clear-v452')return;
  const kind=d.kind==='chat'||d.kind==='notice'?d.kind:'all';
  event.waitUntil((async()=>{
    let found=0,closed=0;
    try{
      const list=await self.registration.getNotifications();
      found=list.length;
      list.forEach(n=>{
        try{
          if(kind==='all'||(kind==='chat'&&isChatV452(n))||(kind==='notice'&&!isChatV452(n))){n.close();closed++;}
        }catch{}
      });
    }catch{}
    if(kind==='all'){try{await self.navigator?.clearAppBadge?.();}catch{}}
    // 消すものがあったときだけ残す（何もないときに記録が埋まらないように）
    if(found>0)await addLog({ev:'PORTALから消す',kind,found,closed});
  })());
});

// v456: 通知を指で消したとき（スワイプ・すべて消去）
self.addEventListener('notificationclose',event=>{
  event.waitUntil(addLog({ev:'指で消した',tag:String(event.notification?.tag||'').slice(0,40)}));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    await addLog({ev:'タップ',tag:String(event.notification?.tag||'').slice(0,40)});
    const target=allowedPage(event.notification?.data?.url);
    const windows=await clients.matchAll({type:'window',includeUncontrolled:true});
    const current=windows.find(w=>{
      try{const url=new URL(w.url);return url.origin===PORTAL_URL.origin&&url.pathname===PORTAL_URL.pathname;}
      catch{return false;}
    });
    if(current){
      try{
        // Navigate through the existing portal authorization flow; the pushTo
        // param opens chat/notices only after the existing identity gate passes.
        const page=await current.navigate(target);
        await (page||current).focus();
        return;
      }catch{/* Open a new portal window if the previous one became unavailable. */}
    }
    await clients.openWindow(target);
  })());
});
