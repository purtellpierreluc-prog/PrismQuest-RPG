/* Short compositor effects observe existing renders, never gate combat. */
(() => {
  'use strict';
  if (window.PrismEncounter) return;
  let previous = null, envelope = null, generation = 0, queued = false;
  const animations = new Set(), painted = new WeakMap();
  const counts = {arrival:0, victory:0, defeat:0, fled:0};
  const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
  function cancel() {
    for (const animation of animations) animation.cancel();
    animations.clear();
  }
  function stop() { cancel(); envelope = null; }
  function reduced(stage, signal) {
    return motionQuery.matches || signal.reduced || document.documentElement.dataset.mqReducedMotion === 'true' ||
      !!stage.closest('.mq-a11y-reduce-motion');
  }
  function animate(element, frames, duration, elapsed) {
    if (!element?.animate || elapsed >= duration) return;
    const animation = element.animate(frames, {duration, easing:'cubic-bezier(.18,.75,.25,1)', fill:'both'});
    animation.currentTime = Math.max(0, elapsed);
    animations.add(animation);
    animation.onfinish = () => { animations.delete(animation); animation.cancel(); };
  }
  function paint(stage) {
    if (!envelope || painted.get(stage) === envelope.id) return;
    const elapsed = performance.now() - envelope.start;
    if (elapsed >= 440) { stop(); return; }
    cancel();
    painted.set(stage, envelope.id);
    if (envelope.kind === 'arrival') {
      animate(stage.querySelector('.pd-enemy-art'), [
        {opacity:.28, transform:'translateX(18px) scale(.965)'},
        {opacity:1, transform:'translateX(0) scale(1)'}], 380, elapsed);
      animate(stage.querySelector('.pd-round'), [
        {opacity:.5, transform:'translateY(5px)'}, {opacity:1, transform:'translateY(0)'}], 300, elapsed);
    } else {
      const victory = envelope.kind === 'victory';
      const target = stage.querySelector(victory || envelope.kind === 'fled' ? '.pd-enemy-art' : '.pd-hero-art');
      animate(target, [{opacity:1, transform:'scale(1)'},
        {opacity:victory || envelope.kind === 'fled' ? .52 : .82, transform:'scale(.985)'}], 340, elapsed);
      animate(stage.querySelector('.pd-result-title'), [
        {opacity:.55, transform:'translateY(5px)'}, {opacity:1, transform:'translateY(0)'}], 380, elapsed);
    }
    animate(stage.querySelector('.pd-encounter-trace'), [
      {opacity:0, transform:'scaleX(.7)'}, {opacity:.6, offset:.3}, {opacity:0, transform:'scaleX(1.08)'}], 420, elapsed);
  }
  function read() {
    queued = false;
    const stage = document.querySelector('.pd-battle-theatre[data-pd-encounter]');
    if (!stage) { stop(); previous = null; return; }
    let signal;
    try { signal = JSON.parse(stage.dataset.pdEncounter); } catch (_) { return; }
    const old = previous;
    previous = signal;
    if (!old || old.p !== signal.p) { stop(); return; }
    if (reduced(stage, signal) || document.visibilityState === 'hidden') { stop(); return; }
    let kind = '';
    if (signal.phase === 'combat' && (old.phase !== 'combat' || old.e !== signal.e)) kind = 'arrival';
    else if (old.phase === 'combat' && ['victory','defeat','fled'].includes(signal.phase)) kind = signal.phase;
    if (kind) {
      stop();
      counts[kind] += 1;
      envelope = {id:++generation, kind, start:performance.now()};
    }
    paint(stage);
  }
  function queue() {
    if (!queued) { queued = true; queueMicrotask(read); }
  }
  function start() {
    new MutationObserver(records => {
      const relevant = records.some(r => r.type === 'attributes' || [...r.addedNodes].some(node =>
        node.nodeType === 1 && (node.matches('.mq-desktop,.pd-battle-theatre') || node.querySelector('.pd-battle-theatre'))));
      if (relevant) queue();
    }).observe(document.body, {subtree:true, childList:true, attributes:true, attributeFilter:['data-pd-encounter']});
    new MutationObserver(() => {
      if (document.documentElement.dataset.mqReducedMotion === 'true') stop();
    }).observe(document.documentElement, {attributes:true, attributeFilter:['data-mq-reduced-motion']});
    read();
  }
  motionQuery.addEventListener('change', () => { if (motionQuery.matches) stop(); });
  window.addEventListener('blur', stop);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') stop(); });
  window.PrismEncounter = {inspect:() => ({counts:{...counts}, phase:previous?.phase || '', running:animations.size,
    elapsed:envelope ? performance.now()-envelope.start : null})};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
