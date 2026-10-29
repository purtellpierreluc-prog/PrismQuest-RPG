/* One local audio graph. Existing UI updates carry signals; no audio polling. */
(() => {
  'use strict';
  if (window.PrismAudio) return;
  const defaults = {effects_volume: 35, music_volume: 18, muted: false, music_enabled: true,
    combat_enabled: true, rewards_enabled: true, mute_unfocused: true};
  let config = {...defaults, ...(window.pqAudioInitial || {})};
  let context = null, master = null, effects = null, music = null, undertone = null;
  let boot = null, interacted = false, focused = document.hasFocus(), disposed = false;
  let previous = null, lastLab = null, inCombat = false, lastCombatAt = -Infinity;
  let lastLabCritAt = 0, ducked = false, epoch = 0, lastRewardAt = -Infinity;
  let suspendTimer = 0, duckTimer = 0, rewardTimer = 0, loopStopTimer = 0, previewTicket = 0;
  const buffers = new Map(), loops = new Map(), voices = new Set(), seen = new Set();
  const counts = Object.create(null), failed = new Set();
  const files = ['ambient', 'undertone', 'impact', 'spell', 'critical', 'encounter', 'victory',
    'level', 'find_soft', 'find_rare', 'find_prismatic'];
  const allowed = () => !disposed && !config.muted &&
    (!config.mute_unfocused || (focused && document.visibilityState !== 'hidden'));
  const effectsAllowed = reward => allowed() && config.effects_volume > 0 &&
    (reward ? config.rewards_enabled : config.combat_enabled);
  const anyEnabled = () => !config.muted && ((config.music_enabled && config.music_volume > 0) ||
    (config.effects_volume > 0 && (config.rewards_enabled || config.combat_enabled)));
  const now = () => performance.now();
  function status() {
    const el = document.getElementById('pq-audio-status');
    if (!el) return;
    el.textContent = config.muted ? 'All audio muted.' : !interacted ? 'Audio starts after your first click or keypress.' :
      !allowed() ? 'Quiet while this window is in the background.' : context?.state === 'running' ?
      'Local audio ready. Quiet by default; adjust to taste.' : 'Audio paused or unavailable. Click a preview to try again.';
  }
  function ramp(param, target, seconds = .15) {
    if (!context || !param) return;
    const time = context.currentTime;
    param.cancelScheduledValues(time);
    param.setValueAtTime(param.value, time);
    param.linearRampToValueAtTime(target, time + seconds);
  }
  function remember(key) {
    if (seen.has(key)) return false;
    seen.add(key);
    if (seen.size > 128) seen.delete(seen.values().next().value);
    return true;
  }
  function cancelRewards() {
    clearTimeout(rewardTimer);
    rewardTimer = 0;
    pendingLevel = false;
    pendingLoot = '';
  }
  function stopVoices(includeRewards = true) {
    for (const voice of voices) {
      if (!includeRewards && voice.reward) continue;
      ramp(voice.volume.gain, 0, .035);
      try { voice.source.stop(context.currentTime + .04); } catch (_) { /* already ended */ }
    }
  }
  function stopLoops() {
    for (const source of loops.values()) {
      try { source.stop(); } catch (_) { /* already ended */ }
      source.disconnect();
    }
    loops.clear();
  }
  function startLoops() {
    if (!context || !config.music_enabled || config.music_volume <= 0 || !allowed()) return;
    clearTimeout(loopStopTimer);
    for (const [name, bus] of [['ambient', music], ['undertone', undertone]]) {
      if (loops.has(name) || !buffers.has(name)) continue;
      const source = context.createBufferSource();
      source.buffer = buffers.get(name);
      source.loop = true;
      source.connect(bus);
      source.start(0, context.currentTime % source.buffer.duration);
      loops.set(name, source);
    }
  }
  function applyMix() {
    if (!context) { status(); return; }
    ramp(effects.gain, config.effects_volume / 100, .08);
    const bed = config.music_enabled ? config.music_volume / 100 : 0;
    ramp(music.gain, bed * 1.35 * (ducked ? .42 : 1), .8);
    ramp(undertone.gain, bed * (inCombat ? .36 : 0) * (ducked ? .42 : 1), 1.5);
    if (!config.music_enabled || !config.music_volume) {
      clearTimeout(loopStopTimer);
      loopStopTimer = setTimeout(stopLoops, 900);
    } else startLoops();
    status();
  }
  async function applyFocus() {
    const generation = ++epoch;
    clearTimeout(suspendTimer);
    if (!context) { status(); return; }
    if (!allowed() || !anyEnabled()) {
      cancelRewards();
      ramp(master.gain, 0, .10);
      suspendTimer = setTimeout(async () => {
        if (generation !== epoch || (allowed() && anyEnabled())) return;
        stopVoices();
        try { await context.suspend(); } catch (_) { /* audio must never stop the game */ }
        if (generation !== epoch && allowed() && anyEnabled()) applyFocus();
        status();
      }, 150);
    } else {
      try { await context.resume(); } catch (_) { /* gesture may be required */ }
      if (generation !== epoch || !allowed()) return;
      ramp(master.gain, .85, .22);
      applyMix();
    }
    status();
  }
  async function load(name) {
    try {
      const response = await fetch('/desktop-ui/audio/v1/' + name + '.wav', {cache: 'force-cache'});
      if (!response.ok) throw new Error('Audio asset unavailable');
      const decoded = await context.decodeAudioData(await response.arrayBuffer());
      buffers.set(name, decoded);
    } catch (_) { failed.add(name); }
  }
  function unlock() {
    interacted = true;
    if (disposed || !allowed() || !anyEnabled()) { status(); return Promise.resolve(); }
    if (!context) {
      try {
        const Audio = window.AudioContext || window.webkitAudioContext;
        context = new Audio({latencyHint: 'playback'});
        master = context.createGain(); master.gain.value = 0;
        const limiter = context.createDynamicsCompressor();
        limiter.threshold.value = -12; limiter.knee.value = 12; limiter.ratio.value = 8;
        limiter.attack.value = .003; limiter.release.value = .22;
        master.connect(limiter); limiter.connect(context.destination);
        effects = context.createGain(); effects.connect(master);
        music = context.createGain(); music.gain.value = 0; music.connect(master);
        undertone = context.createGain(); undertone.gain.value = 0; undertone.connect(master);
        context.onstatechange = status;
        boot = Promise.all(files.map(load)).then(() => { if (!disposed) { applyMix(); applyFocus(); } });
      } catch (_) {
        context = null;
        status();
        return Promise.resolve();
      }
    }
    // Resume synchronously from a trusted click/keypress, before awaiting assets.
    context.resume().catch(() => {});
    applyFocus();
    return boot || Promise.resolve();
  }
  function duck() {
    ducked = true;
    clearTimeout(duckTimer);
    applyMix();
    duckTimer = setTimeout(() => { ducked = false; applyMix(); }, 2100);
  }
  function play(name, {reward = false, gain = 1, key = ''} = {}) {
    if (!effectsAllowed(reward) || context?.state !== 'running' || !buffers.has(name)) return false;
    if (reward && now()-lastRewardAt < 240) return false;
    if (key && !remember(key)) return false;
    if (!reward && (now()-lastCombatAt < 750 || voices.size >= 3)) return false;
    if (reward) { lastRewardAt = now(); stopVoices(false); duck(); } else lastCombatAt = now();
    if (voices.size >= 4) {
      const oldest = voices.values().next().value;
      ramp(oldest.volume.gain, 0, .035);
      oldest.source.stop(context.currentTime + .04);
      voices.delete(oldest);
    }
    const source = context.createBufferSource(), volume = context.createGain();
    source.buffer = buffers.get(name);
    source.playbackRate.value = reward ? 1 : .985 + Math.random()*.03;
    volume.gain.value = gain;
    source.connect(volume); volume.connect(effects);
    const voice = {source, volume, reward};
    voices.add(voice);
    source.onended = () => { voices.delete(voice); source.disconnect(); volume.disconnect(); };
    source.start();
    counts[name] = (counts[name] || 0) + 1;
    return true;
  }
  let pendingLevel = false, pendingLoot = '';
  function lootSound(rarity) {
    if (rarity === 'Common' || !rarity) return '';
    if (rarity === 'Fine') return 'find_soft';
    return ['Rare', 'Epic'].includes(rarity) ? 'find_rare' : 'find_prismatic';
  }
  function sync(signal) {
    if (!signal || typeof signal !== 'object') return;
    const old = previous;
    previous = signal;
    inCombat = !!signal.a;
    if (!old || old.p !== signal.p || !signal.p) {
      cancelRewards(); lastLab = null; lastLabCritAt = 0;
      stopVoices();
      applyMix();
      return;
    }
    if (old.e !== signal.e || old.s !== signal.s) lastLab = null;
    if (signal.l > old.l) pendingLevel = true;
    if (signal.r > old.r) pendingLoot = lootSound(signal.q);
    if (!allowed() || !interacted) { cancelRewards(); applyMix(); return; }
    if (signal.a && !old.a) play('encounter', {gain: .42});
    if (signal.a && old.a && signal.d > old.d && (signal.h < old.h || signal.m < old.m)) {
      play(signal.c ? 'critical' : signal.k === 'spell' ? 'spell' : 'impact', {gain: .42, key: signal.p + ':' + signal.d});
    }
    if (!signal.a) {
      const level = pendingLevel, loot = pendingLoot;
      pendingLevel = false; pendingLoot = '';
      if (level) {
        play('level', {reward: true, gain: .9, key: signal.p + ':level:' + signal.l});
        if (loot) {
          clearTimeout(rewardTimer);
          rewardTimer = setTimeout(() => {
            if (previous?.p === signal.p) play(loot, {reward: true, gain: .58, key: signal.p + ':loot:' + signal.r});
          }, 1050);
        }
      } else if (loot) play(loot, {reward: true, gain: .9, key: signal.p + ':loot:' + signal.r});
      else if (old.a && old.s === signal.s && signal.o === 'victory') play('victory', {reward: true, gain: .45, key: signal.p + ':victory:' + signal.e});
    }
    applyMix();
  }
  function combatStep(payload) {
    if (!inCombat || !payload || !Array.isArray(payload.members) || !Array.isArray(payload.monsters)) return;
    const hp = [...payload.members.map(row => Number(row[0])), ...payload.monsters.map(row => Number(row[0]))];
    const dropped = lastLab && hp.length === lastLab.length && hp.some((value, index) => value < lastLab[index]);
    lastLab = hp;
    if (!dropped) return;
    const popups = [...payload.members.map(row => row[5]), ...payload.monsters.map(row => row[2])].filter(Boolean);
    const critical = popups.some(popup => popup.crit && Number(popup.at) > lastLabCritAt);
    lastLabCritAt = Math.max(lastLabCritAt, ...popups.map(popup => Number(popup.at) || 0));
    play(critical ? 'critical' : previous?.k === 'spell' ? 'spell' : 'impact', {gain: .32});
  }
  function configure(next) {
    const update = {};
    for (const key of Object.keys(defaults)) {
      if (!(key in next)) continue;
      update[key] = typeof defaults[key] === 'boolean' ? next[key] === true : Math.max(0, Math.min(100, Number(next[key]) || 0));
    }
    config = {...config, ...update};
    if (!config.rewards_enabled || !config.effects_volume || config.muted) cancelRewards();
    if (!config.effects_volume || config.muted) stopVoices();
    if (interacted && !context && anyEnabled()) unlock();
    applyMix(); applyFocus();
  }
  async function preview(name) {
    if (!files.includes(name)) return;
    const ticket = ++previewTicket;
    await unlock();
    if (ticket !== previewTicket) return;
    if (name === 'ambient') { applyMix(); return; }
    cancelRewards(); stopVoices();
    await new Promise(resolve => setTimeout(resolve, 50));
    if (ticket !== previewTicket) return;
    lastCombatAt = -Infinity; lastRewardAt = -Infinity;
    play(name, {reward: ['level', 'find_soft', 'find_rare', 'find_prismatic', 'victory'].includes(name), gain: .75});
  }
  function close() {
    disposed = true;
    cancelRewards();
    for (const timer of [suspendTimer, duckTimer, loopStopTimer]) clearTimeout(timer);
    stopVoices(); stopLoops();
    if (context && context.state !== 'closed') context.close().catch(() => {});
  }
  const api = {sync, combatStep, configure, preview,
    inspect: () => ({preferences: {...config}, context: context?.state || 'locked', focused, allowed: allowed(),
      decoded: buffers.size, failed: [...failed], voices: voices.size, loops: loops.size, dedupKeys: seen.size, played: {...counts}})};
  window.PrismAudio = api;
  document.addEventListener('pointerdown', unlock, {passive: true});
  document.addEventListener('keydown', event => { if (!event.repeat && !['Shift','Control','Alt','Meta'].includes(event.key)) unlock(); }, {passive: true});
  window.addEventListener('blur', () => { focused = false; applyFocus(); });
  window.addEventListener('focus', () => { focused = true; applyFocus(); });
  document.addEventListener('visibilitychange', applyFocus);
  window.addEventListener('pagehide', close);
  let readQueued = false;
  const read = () => {
    readQueued = false;
    const root = document.querySelector('.mq-desktop[data-pq-audio]');
    if (root) {
      try { sync(JSON.parse(root.dataset.pqAudio)); } catch (_) { /* missing signal never affects gameplay */ }
    }
    status();
  };
  const observer = new MutationObserver(records => {
    if (readQueued) return;
    const relevant = records.some(record => record.type === 'attributes' || [...record.addedNodes].some(node =>
      node.nodeType === 1 && (node.matches('.mq-desktop[data-pq-audio], #pq-audio-status') ||
      node.querySelector('.mq-desktop[data-pq-audio], #pq-audio-status'))));
    if (relevant) { readQueued = true; queueMicrotask(read); }
  });
  const start = () => { observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['data-pq-audio']}); read(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
