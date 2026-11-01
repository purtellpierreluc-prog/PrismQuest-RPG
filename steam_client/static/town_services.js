/* Finite local receipts. No extra timers, polling, game actions or socket frames. */
(() => {
  'use strict';
  if(window.PrismTown)return;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)'),ledger=new Map(),bound=new WeakSet(),active=new Map(),scrolls=new Map(),scrollBound=new WeakSet();
  let queued=false,reveals=0,pendingFocus=null;
  function stop(){for(const effect of active.values())effect.cancel();active.clear();}
  function read(){
    queued=false;
    for(const [node,effect] of active){if(!node.isConnected){effect.cancel();active.delete(node);}}
    for(const panel of document.querySelectorAll('[data-town-scroll]')){
      if(scrollBound.has(panel))continue;
      scrollBound.add(panel);const key=panel.dataset.townScroll;
      panel.scrollTop=scrolls.get(key)||0;
      panel.addEventListener('scroll',()=>{scrolls.set(key,panel.scrollTop);if(scrolls.size>64)scrolls.delete(scrolls.keys().next().value);},{passive:true});
    }
    if(pendingFocus&&!pendingFocus.node.isConnected){
      const next=[...document.querySelectorAll('[data-town-item]')].find(e=>e.dataset.townItem===pendingFocus.key);
      if(next&&document.activeElement===document.body)next.focus({preventScroll:true});
      pendingFocus=null;
    }
    for(const node of document.querySelectorAll('[data-town-receipt]')){
      if(bound.has(node))continue;
      bound.add(node);
      let signal;try{signal=JSON.parse(node.dataset.townReceipt);}catch(_){continue;}
      if(!ledger.has(signal.key)){ledger.set(signal.key,performance.now());reveals++;if(ledger.size>64)ledger.delete(ledger.keys().next().value);}
      const elapsed=performance.now()-ledger.get(signal.key);
      if(elapsed>=750||reduce.matches||signal.reduced||document.documentElement.dataset.mqReducedMotion==='true'||document.hidden||!node.animate)continue;
      const effect=node.animate([{opacity:.6,borderColor:'#dfc38a',transform:'translateY(3px)'},{opacity:1,borderColor:'#82794f55',transform:'translateY(0)'}],{duration:750,easing:'cubic-bezier(.15,.7,.3,1)'});
      effect.currentTime=elapsed;active.set(node,effect);effect.onfinish=()=>active.delete(node);
    }
  }
  const queue=()=>{if(!queued){queued=true;queueMicrotask(read);}};
  document.addEventListener('click',event=>{const row=event.target.closest?.('[data-town-item]');if(row)pendingFocus={node:row,key:row.dataset.townItem};},true);
  document.addEventListener('keydown',event=>{
    if(!['ArrowUp','ArrowDown'].includes(event.key)||!event.target.matches?.('[data-town-item]'))return;
    const rows=[...event.target.closest('[data-town-scroll]').querySelectorAll('[data-town-item]')],index=rows.indexOf(event.target);
    event.preventDefault();rows[Math.max(0,Math.min(rows.length-1,index+(event.key==='ArrowDown'?1:-1)))]?.focus({preventScroll:false});
  });
  const start=()=>{new MutationObserver(records=>{if(records.some(r=>[...r.addedNodes,...r.removedNodes].some(n=>n.nodeType===1&&(n.matches('[data-town-receipt],[data-town-scroll]')||n.querySelector('[data-town-receipt],[data-town-scroll]')))))queue();}).observe(document.body,{subtree:true,childList:true});queue();};
  reduce.addEventListener('change',()=>{if(reduce.matches)stop();});
  window.addEventListener('blur',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.PrismTown={inspect:()=>({reveals,active:active.size})};
})();
