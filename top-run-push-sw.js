/* TOP RUN PORTAL - Android/desktop notification receiver.
   One existing-origin, narrowly-scoped Service Worker; no Firebase or secrets.
   Installed ONLY from TOP_RUN_PORTAL Stage3 notification settings, after identity eligibility.
   v452: PORTALで既読になったとき、この受け口自身が出した通知とバッジを消す（message 'tr-clear-v452'）。
*/
'use strict';
const PORTAL='https://nuritakug-cpu.github.io/tabirun-bgm/TOP_RUN_PORTAL.html';
const PORTAL_URL=new URL(PORTAL);
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
    let value={};
    try{value=event.data?.json()||{};}catch{/* Invalid payload: use generic notification. */}
    const n=value?.notification&&typeof value.notification==='object'?value.notification:value;
    const title=typeof n?.title==='string'?n.title.slice(0,80):'TOP RUN';
    const body=typeof n?.body==='string'?n.body.slice(0,220):'新しい通知があります。';
    const navigate=allowedPage(n?.navigate);
    await self.registration.showNotification(title,{
      body,lang:'ja',dir:'auto',tag:typeof n?.tag==='string'?n.tag.slice(0,70):'top-run-message',
      data:{url:navigate},silent:n?.silent===true
    }); const badge=Number.isSafeInteger(value?.badge)&&value.badge>=0?value.badge:1;try{if(badge===0){await self.navigator?.clearAppBadge?.();}else{await self.navigator?.setAppBadge?.(badge);}}catch{}
  })());
});
// v452: PORTALの既読に合わせて、この受け口が出した通知とバッジを消す。
const isChatV452=n=>/chat|room|チャット|ルーム/.test([n.tag,n.title,n.body,JSON.stringify(n.data||{})].join(' ').toLowerCase());
self.addEventListener('message',event=>{
  const d=event.data;
  if(!d||d.type!=='tr-clear-v452')return;
  const kind=d.kind==='chat'||d.kind==='notice'?d.kind:'all';
  event.waitUntil((async()=>{
    try{
      const list=await self.registration.getNotifications();
      list.forEach(n=>{
        try{
          if(kind==='all'||(kind==='chat'&&isChatV452(n))||(kind==='notice'&&!isChatV452(n)))n.close();
        }catch{}
      });
    }catch{}
    if(kind==='all'){try{await self.navigator?.clearAppBadge?.();}catch{}}
  })());
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil((async()=>{
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
