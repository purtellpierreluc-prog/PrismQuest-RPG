/* Phase changes, not frame polling. No hidden answers or progression live here. */
(() => {
  'use strict';
  if (window.PrismChapters) return;
  const seen = new Set(), motions = new Set(), reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const cues = {threshold:'story_threshold',judging:'story_judging',matched:'story_binding',failure:'story_fracture',success:'story_ascend',final:'story_complete'};
  let queued = false, stage = null, phase = '', events = 0;
  function cancel() { for (const effect of motions) effect.cancel(); motions.clear(); }
  function animate(node,frames,duration,delay=0) {
    if (!node?.animate) return;
    const effect = node.animate(frames,{duration,delay,easing:'cubic-bezier(.2,.65,.25,1)',fill:'both'});
    motions.add(effect);
    effect.onfinish = () => { motions.delete(effect); effect.cancel(); };
  }
  function once(key) {
    if (seen.has(key)) return false;
    seen.add(key); if (seen.size>128) seen.delete(seen.values().next().value);
    return true;
  }
  function read() {
    queued = false;
    const root = document.querySelector('[data-ps-signal]');
    if (stage !== root) { cancel(); stage = root; }
    if (!root) { phase=''; window.PrismAudio?.scoreScene?.(''); }
    else {
      let signal; try { signal=JSON.parse(root.dataset.psSignal); } catch (_) { return; }
      phase=signal.phase;
      window.PrismAudio?.scoreScene?.(['success','failure','final'].includes(phase)?'aftermath':'rite');
      if (once(signal.key+':'+signal.step+':'+phase)) {
        events++;
        const cue=cues[phase];
        if (cue) window.PrismAudio?.chapter?.(cue,signal.key+':'+signal.step+':'+phase);
        if (document.visibilityState !== 'hidden' && !reduce.matches && !signal.reduced) {
          if (phase==='judging') {
            animate(root.querySelector('.ps-prism-stage .ps-prism'),[{opacity:1,transform:'translateX(-50%) scale(1)'},{opacity:.48,transform:'translateX(-50%) scale(.96)',offset:.65},{opacity:.9,transform:'translateX(-50%) scale(1)'}],1050);
            animate(root.querySelector('.ps-prism-trace'),[{opacity:0,transform:'translateX(-50%) scaleX(.2)'},{opacity:.65,offset:.6},{opacity:0,transform:'translateX(-50%) scaleX(1)'}],1050);
          } else if (phase==='matched'||phase==='rejected') {
            const target=[...root.querySelectorAll('[data-ps-vessel]')].find(e=>e.dataset.psVessel===signal.vessel);
            animate(target,[{opacity:1,transform:'scale(1)'},{opacity:.5,transform:'scale(.965)'},{opacity:1,transform:'scale(1)'}],400);
          } else if (['success','failure','final'].includes(phase)) {
            const win=phase!=='failure',duration=phase==='final'?1900:1400;
            animate(root.querySelector('.ps-legacy-hero'),[{opacity:.1,transform:'translateY(14px) scale(.96)'},{opacity:1,transform:'translateY(0) scale(1)'}],duration,100);
            animate(root.querySelector('.ps-outcome-title'),[{opacity:0,transform:'translateY(16px)'},{opacity:1,transform:'translateY(0)'}],1000,350);
            animate(root.querySelector('.ps-outcome-story'),[{opacity:0,transform:'translateY(9px)'},{opacity:1,transform:'translateY(0)'}],850,850);
            if (win) animate(root.querySelector('.ps-aftermath-ray'),[{opacity:0,transform:'scaleY(.4)'},{opacity:.8,offset:.4},{opacity:0,transform:'scaleY(1)'}],duration+600);
            root.querySelector('.ps-outcome-title')?.focus({preventScroll:true});
          } else if (phase==='threshold') {
            animate(root.querySelector('.ps-threshold-poem'),[{opacity:.2,transform:'translateY(12px)'},{opacity:1,transform:'translateY(0)'}],850);
          }
        }
      }
    }
    const receipt=document.querySelector('[data-pm-receipt]');
    if (receipt) {
      let data;try{data=JSON.parse(receipt.dataset.pmReceipt);}catch(_){return;}
      if (once('purchase:'+data.key)) {
        window.PrismAudio?.chapter?.('story_purchase',data.key);
        if (!reduce.matches&&!data.reduced) animate(receipt,[{opacity:.45,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],650);
      }
    }
  }
  function queue(){if(!queued){queued=true;queueMicrotask(read);}}
  const observer=new MutationObserver(records=>{
    if(stage&&!stage.isConnected){cancel();stage=null;}
    if(records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches('[data-ps-signal],[data-pm-receipt]')||n.querySelector('[data-ps-signal],[data-pm-receipt]'))))||(!document.querySelector('[data-ps-signal]')&&phase))queue();
  });
  document.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight'].includes(event.key)||!event.target.matches('[data-ps-essence],[data-ps-vessel]'))return;
    const container=event.target.parentElement,rows=[...container.querySelectorAll('button:not([disabled])')];
    const i=rows.indexOf(event.target),next=rows[Math.max(0,Math.min(rows.length-1,i+(event.key==='ArrowRight'?1:-1)))];
    event.preventDefault();next?.focus({preventScroll:true});
  });
  window.addEventListener('blur',cancel);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')cancel();});
  reduce.addEventListener('change',()=>{if(reduce.matches)cancel();});
  const start=()=>{observer.observe(document.body,{subtree:true,childList:true});queue();};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.PrismChapters={inspect:()=>({phase,events,animations:motions.size})};
})();
