/* Stable shelf and a saved-result reveal. No combat authority or frame polling. */
(() => {
  'use strict';
  if(window.PrismWell)return;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'),scrolls=new Map(),seen=new Set(),ledger=new Map();
  let queued=false,active=null,activeKey='',motions=[],reveals=0,skipped=0;
  try{for(const key of JSON.parse(sessionStorage.getItem('pq-well-reveals')||'[]'))seen.add(key);}catch(_){/* optional presentation memory */}
  function finish(remember=true){for(const effect of motions)effect.cancel();motions=[];active?.classList.remove('pw-revealing');active=null;if(remember&&activeKey){seen.add(activeKey);if(seen.size>64)seen.delete(seen.values().next().value);try{sessionStorage.setItem('pq-well-reveals',JSON.stringify([...seen]));}catch(_){/* optional presentation memory */}activeKey='';}}
  function animate(node,frames,duration,delay=0,elapsed=0){if(!node?.animate)return;const effect=node.animate(frames,{duration,delay,easing:'cubic-bezier(.2,.65,.25,1)',fill:'both'});effect.currentTime=elapsed;motions.push(effect);return effect;}
  function read(){
    queued=false;
    if(active&&!active.isConnected)finish(false);
    const shelf=document.querySelector('[data-pw-shelf]');
    if(shelf&&!shelf.dataset.pwBound){
      const key=shelf.dataset.pwShelf+':'+shelf.dataset.pwFilter;
      shelf.scrollTop=scrolls.get(key)||0;shelf.dataset.pwBound='true';
      shelf.addEventListener('scroll',()=>{scrolls.set(key,shelf.scrollTop);if(scrolls.size>32)scrolls.delete(scrolls.keys().next().value);},{passive:true});
    }
    const result=document.querySelector('[data-pw-result]');
    if(!result){finish();return;}
    let signal;try{signal=JSON.parse(result.dataset.pwResult);}catch(_){return;}
    if(seen.has(signal.key))return;
    if(activeKey&&activeKey!==signal.key)finish();
    activeKey=signal.key;
    if(!ledger.has(signal.key)){ledger.set(signal.key,performance.now());reveals++;if(ledger.size>64)ledger.delete(ledger.keys().next().value);}
    if(reduced.matches||signal.reduced||document.hidden||['defeat','fled'].includes(signal.outcome)){finish();return;}
    if(active===result)return;
    finish(false);activeKey=signal.key;active=result;result.classList.add('pw-revealing');
    const ranks=['Common','Fine','Rare','Epic','Mythic','Ancient','Relic','Ascendant','Legendary','Unspawnable'];
    const strength=Math.max(0,ranks.indexOf(signal.rarity)),duration=900+strength*115;
    const elapsed=performance.now()-ledger.get(signal.key);
    if(elapsed>=duration+450){finish();return;}
    const cover=animate(result.querySelector('.pw-answer-veil'),[{opacity:1},{opacity:1,offset:.25},{opacity:0}],duration,450,elapsed);
    animate(result.querySelector('.pw-ripple'),[{transform:'scale(.6)',opacity:.3},{transform:'scale(1.35)',opacity:1,offset:.55},{transform:'scale(1.8)',opacity:0}],duration,450,elapsed);
    animate(result.querySelector('.pw-answer-body'),[{opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],650,650,elapsed);
    result.querySelectorAll('.mq-affix-line').forEach((row,i)=>animate(row,[{opacity:0,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],550,750+Math.min(i,7)*80,elapsed));
    if(cover)cover.onfinish=finish;else finish();
  }
  const queue=()=>{if(!queued){queued=true;queueMicrotask(read);}};
  document.addEventListener('click',event=>{if(event.target.closest?.('[data-pw-skip]')){skipped++;finish();}});
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&active){skipped++;finish();return;}
    if(!['ArrowUp','ArrowDown'].includes(event.key)||!event.target.matches('[data-pw-item]'))return;
    const rows=[...event.target.parentElement.querySelectorAll('[data-pw-item]:not([disabled])')],i=rows.indexOf(event.target);
    event.preventDefault();rows[Math.max(0,Math.min(rows.length-1,i+(event.key==='ArrowDown'?1:-1)))]?.focus({preventScroll:false});
  });
  window.addEventListener('blur',finish);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)finish();});
  reduced.addEventListener('change',()=>{if(reduced.matches)finish();});
  const start=()=>{new MutationObserver(records=>{const removed=active&&!active.isConnected;if(removed)finish(false);if(removed||records.some(record=>[...record.addedNodes].some(node=>node.nodeType===1&&(node.matches('[data-pw-shelf],[data-pw-result]')||node.querySelector('[data-pw-shelf],[data-pw-result]')))))queue();}).observe(document.body,{subtree:true,childList:true});queue();};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.PrismWell={inspect:()=>({reveals,skipped,active:!!active,animations:motions.length})};
})();
