/* Cosmetic feedback only: never synthesize an action or wait for an animation. */
(() => {
  'use strict';
  if(window.PrismControls)return;
  const selector='.q-btn:is(.mq-btn-gold,.mq-btn-secondary,.mq-btn-danger,.mq-btn-affirm,.mq-arena-btn-primary,.pq-menu-play):not([aria-pressed]):not(.pd-destination,.pd-service,.pc-slot)';
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  let pressed=null,effect=null,presses=0;
  function valid(button){return button&&!button.disabled&&button.getAttribute('aria-disabled')!=='true'&&!button.classList.contains('disabled');}
  function release(animate=true){
    const button=pressed;pressed=null;
    if(!button)return;
    button.classList.remove('pq-press');
    if(effect){effect.cancel();effect=null;}
    if(!animate||!valid(button)||!button.isConnected||reduce.matches||document.querySelector('.mq-a11y-reduce-motion'))return;
    const content=button.querySelector('.q-btn__content');
    if(content?.animate){effect=content.animate([{transform:'translateY(.7px)',opacity:.91},{transform:'translateY(0)',opacity:1}],{duration:155,easing:'cubic-bezier(.2,.75,.3,1)'});effect.onfinish=()=>{effect=null;};}
  }
  function press(button){
    release(false);
    if(!valid(button))return;
    pressed=button;presses++;button.classList.add('pq-control','pq-press');
  }
  document.addEventListener('pointerover',event=>{event.target.closest?.(selector)?.classList.add('pq-control');},{passive:true});
  document.addEventListener('focusin',event=>{event.target.closest?.(selector)?.classList.add('pq-control');});
  document.addEventListener('pointerdown',event=>{if(event.button===0)press(event.target.closest?.(selector));},{passive:true});
  document.addEventListener('pointerup',()=>release(),{passive:true});
  document.addEventListener('pointercancel',()=>release(false),{passive:true});
  document.addEventListener('keydown',event=>{if(!event.repeat&&['Enter',' '].includes(event.key))press(event.target.closest?.(selector));});
  document.addEventListener('keyup',event=>{if(['Enter',' '].includes(event.key))release();});
  window.addEventListener('blur',()=>release(false));
  document.addEventListener('visibilitychange',()=>{if(document.hidden)release(false);});
  window.PrismControls={inspect:()=>({presses,pressed:!!pressed,animating:!!effect})};
})();
