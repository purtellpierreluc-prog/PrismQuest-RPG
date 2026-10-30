/* Read-only equipment inspection lives outside refreshable combat panels. */
(() => {
  'use strict';
  if (window.pdItemInspection) return;
  const selector = '[data-pd-inspect-key]';
  let overlay = null, key = '', anchor = null, hideTimer = 0, queued = false;
  let pointer = {x: -1, y: -1}, keyboard = false;
  function target() {
    if (overlay) return overlay;
    overlay = document.createElement('aside');
    overlay.id = 'pd-item-inspection';
    overlay.className = 'mq-item-hover-floating pd-item-inspection';
    overlay.setAttribute('role', 'tooltip');
    overlay.hidden = true;
    document.body.appendChild(overlay);
    overlay.addEventListener('pointerenter', () => clearTimeout(hideTimer));
    overlay.addEventListener('pointerleave', scheduleHide);
    return overlay;
  }
  function place() {
    if (!anchor?.isConnected || !overlay || overlay.hidden) return;
    const a = anchor.getBoundingClientRect(), b = overlay.getBoundingClientRect();
    const left = Math.max(12, Math.min(a.left, innerWidth - b.width - 12));
    const above = a.top - b.height - 12;
    const top = above >= 12 ? above : Math.min(innerHeight - b.height - 12, a.bottom + 12);
    overlay.style.left = Math.round(left) + 'px';
    overlay.style.top = Math.max(12, Math.round(top)) + 'px';
  }
  function hide() {
    clearTimeout(hideTimer);
    if (overlay) overlay.hidden = true;
    if (anchor) anchor.removeAttribute('aria-describedby');
    key = ''; anchor = null; keyboard = false;
  }
  function scheduleHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 140);
  }
  function show(el, fromKeyboard = false) {
    const content = el?.querySelector('.pd-inspect-content');
    if (!content) return;
    clearTimeout(hideTimer);
    if (anchor && anchor !== el) anchor.removeAttribute('aria-describedby');
    anchor = el; key = el.dataset.pdInspectKey; keyboard = fromKeyboard;
    const box = target();
    if (box.innerHTML !== content.innerHTML) box.innerHTML = content.innerHTML;
    box.hidden = false;
    el.setAttribute('aria-describedby', box.id);
    place();
  }
  function reconcile() {
    queued = false;
    if (!key || !document.body) return;
    const next = [...document.querySelectorAll(selector)].find(el => el.dataset.pdInspectKey === key);
    if (!next) { hide(); return; }
    const rect = next.getBoundingClientRect();
    const inside = pointer.x >= rect.left && pointer.x <= rect.right && pointer.y >= rect.top && pointer.y <= rect.bottom;
    if (inside || overlay?.matches(':hover') || (keyboard && document.activeElement === next)) show(next, keyboard);
    else hide();
  }
  function start() {
    document.addEventListener('pointermove', e => { pointer = {x:e.clientX, y:e.clientY}; }, {passive:true});
    document.addEventListener('pointerover', e => {
      pointer = {x:e.clientX, y:e.clientY};
      const el = e.target.closest(selector);
      if (el) show(el);
    });
    document.addEventListener('pointerout', e => {
      const el = e.target.closest(selector);
      if (el && !el.contains(e.relatedTarget) && !overlay?.contains(e.relatedTarget)) scheduleHide();
    });
    document.addEventListener('focusin', e => { const el=e.target.closest(selector); if (el) show(el, true); });
    document.addEventListener('focusout', e => { if (e.target.closest(selector)) scheduleHide(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
    window.addEventListener('blur', hide);
    window.addEventListener('resize', place, {passive:true});
    document.addEventListener('scroll', place, {passive:true, capture:true});
    new MutationObserver(records => {
      if (!key || queued || !records.some(r => !overlay?.contains(r.target))) return;
      queued = true; queueMicrotask(reconcile);
    }).observe(document.body, {childList:true, subtree:true});
  }
  window.pdItemInspection = {hide};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
