(() => {
  if (window.__mqDesktopKeysBound) return;
  window.__mqDesktopKeysBound = true;
  let resizeFrame = 0;
  const fitSmallWindow = () => {
    resizeFrame = 0;
    const scale = Math.min(1, innerWidth / 960, innerHeight / 600);
    document.documentElement.style.setProperty('--mq-desktop-scale', String(scale));
  };
  fitSmallWindow();
  window.addEventListener('resize', () => {
    if (!resizeFrame) resizeFrame = requestAnimationFrame(fitSmallWindow);
  }, {passive: true});
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'F11' || event.repeat) return;
    const button = document.getElementById('mq-desktop-fullscreen');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    button.click();
  }, true);
})();
