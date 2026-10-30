/* A committed result is already saved. These bounded effects only present it. */
(() => {
  'use strict';
  if (window.PrismCrucible) return;
  const seen = new Set(), motion = matchMedia('(prefers-reduced-motion: reduce)');
  let active = null, queued = false, scrollTop = 0, focusedOffering = '';
  let reveals = 0, skipped = 0;
  function focusResult(result) {
    if (result?.isConnected && document.hasFocus() && (document.activeElement === document.body || document.activeElement?.matches('[data-pc-skip]'))) {
      result.querySelector('.pc-result-name')?.focus({preventScroll:true});
    }
  }
  function finish() {
    if (!active) return;
    for (const timer of active.timers) clearTimeout(timer);
    for (const animation of active.animations) animation.cancel();
    active.veil?.remove();
    active.sheen?.remove();
    active.result.classList.remove('pc-revealing');
    focusResult(active.result);
    for (const row of document.querySelectorAll('.pc-new-forged')) row.classList.remove('pc-new-forged');
    active = null;
  }
  function animate(element, frames, duration, delay = 0) {
    if (!element?.animate || !active) return;
    const effect = element.animate(frames, {duration, delay, easing:'cubic-bezier(.2,.7,.25,1)', fill:'both'});
    active.animations.push(effect);
  }
  function later(callback, delay) {
    active.timers.push(setTimeout(callback, delay));
  }
  function sound(signal) {
    window.PrismAudio?.ritual?.(signal.rarity, signal.key);
  }
  function read() {
    queued = false;
    const library = document.querySelector('.pc-library-scroll');
    if (library && !library.dataset.pcRestored) {
      library.dataset.pcRestored = 'true';
      library.scrollTop = scrollTop;
      if (focusedOffering) {
        const row = [...library.querySelectorAll('[data-pc-item]')].find(node => node.dataset.pcItem === focusedOffering);
        if (row && !row.disabled && (!document.activeElement || document.activeElement === document.body)) row.focus({preventScroll:true});
      }
    }
    const result = document.querySelector('.pc-result[data-pc-result]');
    if (active && (active.result !== result || !active.result.isConnected)) finish();
    for (const row of document.querySelectorAll('.pc-new-forged')) {
      if (seen.has(row.dataset.pcForged) && (!active || active.key !== row.dataset.pcForged)) row.classList.remove('pc-new-forged');
    }
    if (!result) return;
    let signal;
    try { signal = JSON.parse(result.dataset.pcResult); } catch (_) { return; }
    if (!signal.key || seen.has(signal.key)) return;
    seen.add(signal.key);
    if (seen.size > 96) seen.delete(seen.values().next().value);
    reveals += 1;
    const reduced = motion.matches || signal.reduced || document.documentElement.dataset.mqReducedMotion === 'true' || result.closest('.mq-a11y-reduce-motion');
    if (document.visibilityState === 'hidden') {
      for (const row of document.querySelectorAll('.pc-new-forged')) row.classList.remove('pc-new-forged');
      return;
    }
    if (reduced || !result.animate) {
      for (const row of document.querySelectorAll('.pc-new-forged')) row.classList.remove('pc-new-forged');
      focusResult(result);
      sound(signal); return;
    }
    finish();
    const veil = document.createElement('div');
    veil.className = 'pc-reveal-veil';
    veil.setAttribute('aria-hidden', 'true');
    veil.textContent = 'The fire remembers.';
    result.append(veil);
    const sheen = document.createElement('div');
    sheen.className = 'pc-result-sheen';
    sheen.setAttribute('aria-hidden','true');
    result.append(sheen);
    active = {result, veil, sheen, key:signal.key, timers:[], animations:[]};
    result.classList.add('pc-revealing');
    const rank = Math.max(0,Math.min(8,Number(signal.rank) || 0));
    const delay = 850 + Math.max(0, rank) * 65;
    animate(veil, [{opacity:1}, {opacity:1,offset:.65}, {opacity:0}], delay + 400);
    animate(result.querySelector('.pc-result-crown'), [
      {opacity:0, transform:'translateY(12px) scale(.95)'},
      {opacity:1, transform:'translateY(0) scale(1.025)', offset:.7},
      {opacity:1, transform:'translateY(0) scale(1)'}], 680, delay);
    animate(sheen,[{opacity:0,transform:'translateX(-100%)'},{opacity:signal.up ? .24 : .13,offset:.4},
      {opacity:0,transform:'translateX(110%)'}],800+rank*65,delay+250);
    const rows = [...result.querySelectorAll('.pc-result-stats .mq-base-stat-list, .pc-result-stats .pd-eyebrow, .pc-result-stats .mq-affix-line, .pc-result-location')];
    rows.forEach((row,index) => animate(row, [{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}], 440, delay + 420 + index * 140));
    const stage = document.querySelector('.pc-ritual-stage');
    animate(stage?.querySelector('.pc-orbit'), [{opacity:.2,transform:'translate(-50%,-50%) rotate(-18deg) scale(1.12)'},
      {opacity:1,transform:'translate(-50%,-50%) rotate(24deg) scale(.82)', offset:.7},
      {opacity:.65,transform:'translate(-50%,-50%) rotate(45deg) scale(1)'}], delay + 450);
    animate(stage?.querySelector('.pc-convergence'), [{opacity:0,transform:'translate(-50%,-50%) scale(.3)'},
      {opacity:.75,transform:'translate(-50%,-50%) scale(1.15)',offset:.65},
      {opacity:0,transform:'translate(-50%,-50%) scale(1.5)'}], delay + 650);
    later(() => sound(signal), delay + 150);
    later(finish, Math.min(3400, delay + 1200 + rows.length * 140));
  }
  function queue() { if (!queued) { queued = true; queueMicrotask(read); } }
  document.addEventListener('scroll', event => {
    if (event.target?.matches?.('.pc-library-scroll')) scrollTop = event.target.scrollTop;
  }, {capture:true, passive:true});
  document.addEventListener('focusin', event => {
    if (event.target?.matches?.('[data-pc-item]')) focusedOffering = event.target.dataset.pcItem;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && active) { skipped++; finish(); return; }
    if (!['ArrowUp','ArrowDown'].includes(event.key) || !event.target?.matches?.('[data-pc-item]')) return;
    const library = event.target.closest('.pc-library-scroll');
    const rows = [...library.querySelectorAll('[data-pc-item]:not([disabled]):not(.pc-new-forged)')];
    const index = rows.indexOf(event.target), next = rows[Math.max(0,Math.min(rows.length-1,index+(event.key === 'ArrowDown' ? 1 : -1)))];
    event.preventDefault();
    next?.focus({preventScroll:true}); next?.scrollIntoView({block:'nearest'});
  });
  document.addEventListener('click', event => { if (event.target.closest?.('[data-pc-skip]')) { skipped++; finish(); } });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') finish(); });
  window.addEventListener('blur', finish);
  motion.addEventListener('change', () => { if (motion.matches) finish(); });
  const observer = new MutationObserver(records => {
    if (active && !active.result.isConnected) finish();
    if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 &&
      (node.matches('.pc-result,.pc-library-scroll') || node.querySelector('.pc-result,.pc-library-scroll'))))) queue();
  });
  const start = () => { observer.observe(document.body,{childList:true,subtree:true}); queue(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
  window.addEventListener('pagehide',finish);
  window.PrismCrucible = {skip:finish,inspect:() => ({reveals,skipped,active:!!active,animations:active?.animations.length || 0})};
})();
