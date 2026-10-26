# Desktop Alpha 0.3.0 Verification

Date: 2026-10-26. Windows 11 x64, Python 3.12.14, pinned NiceGUI 3.18.0.
Working scope: offline Windows solo with companions. Web main and production data untouched.
Rollback: Git tag `steam-alpha-v0.2.0`, plus the complete previous executable folder
in `.build-backups/steam-0.2.0-c180079/PrismQuest`.

## Automated Evidence

- 134 pytest tests pass. Includes 31 inherited regressions, save/display/build/
  transport checks, and new schema/transaction/progression/diagnostic/release tests.
- Ruff and pip dependency checks pass. Git whitespace check is part of closeout.
- Save-format 1-to-2 upgrade is lossless at the storage boundary. Future formats,
  malformed economy data, externally replaced/deleted saves, and failed atomic
  writes are refused without replacing the last valid save.
- Failure injection for sale, bulk sale, equip, saved-set move, vault deposit,
  deletion, vault purchase, transmutation, and companion gear transfer restores
  staged ownership/gold. Transaction rollback also restores local service counters.
- Randomized 240 item moves with repeated disk reopen preserve item counts,
  including separate legitimately identical items. Equal-stat saved-set items are
  no longer deleted when transferring a different copy to a companion.
- All 18 classes level/serialize through 60 and Lab level 61. Arena combat runs
  at levels 1/15/30/45/60 for the known roster. These are model checks, not balance
  approval or a player-driven level-1-to-60 playthrough.
- Complete automatic prestige-path check preserves paid companions and other
  chronicles. Final apex completion retains the current hero. Distinct local
  seasons cannot trigger web-style global resets.
- A full 7x7 exploration/boss/three-choice/reward/next-floor integration loop
  completes. That mechanics test sets monster HP low; it is not a difficulty test.
- Tank toggling preserves stable party order and pressed state through repeated
  slot/profile updates, including tied join timestamps.
- Native page reloads reuse one live SessionState rather than creating stale
  parallel character writers. Stale-round idempotency checks still pass.

## Packaged Checks

- PyInstaller build completes with version 0.3.0/0.3.0.0 and generated notices,
  dependency metadata, asset-rights review CSV, and SHA-256 inventory.
- Final 953-file package inventory passes with no changed/unexpected files;
  bundled game source and desktop CSS hashes match source. Packaged diagnostic
  and integrity CLI options pass without starting gameplay.
- Packaged title/Arena/town layouts pass at 1280x720, 1366x768, 1920x1080,
  960x600, 2560x1080, and scaled 800x500. No main-page overflow, contained title
  art, visible primary controls, and functional tutorial/Rare introductory fight.
- Packaged services, inventory, saved sets, vault, five-member Lab map, Tank,
  stable inventory hover/Close, and arrow-key movement checks pass. External
  HTTP requests are blocked during the browser checks; none were attempted and
  no JavaScript page errors occurred.
- Final packaged bulk-sale confirmation sells 30 fixture items for exactly 486
  gold, preserves vault/equipped items, and survives a page reload without errors.
- Settings reduced-motion toggle, persistence across page reload, diagnostics
  export, and 960x600 settings layout pass. Quasar loopback controls require
  awaiting the server-confirmed state, not immediate client-side checkbox state.
- A real previous-alpha disposable format-1 profile opens in the packaged game,
  upgrades to format 2, preserves identity/XP/gold/inventory/equipment, and retains
  the exact original file in a rotating backup.
- Hidden native startup passes outside the tool sandbox: 1084x681 client viewport,
  content height 681, title art and fullscreen control present. Both old and new
  builds timed out inside the sandbox. The smoke runner now rejects a missing
  validation result even if the process otherwise exits cleanly.

## Performance Evidence

Profiling identified repeated saved-checkpoint normalization in local Lab HUD
construction. Desktop-only projections now use live character state and avoid
that public-profile path; combat rules, damage, rewards, and pacing are unchanged.

The same 150-round/40-encounter/5-member/100-inventory-item cProfile workload
changed from 20.30s wall / 19.44s CPU to 11.07s wall / 10.25s CPU. Round p95
changed from 223.86ms to 105.59ms. These are local instrumented measurements,
not a universal FPS/performance promise. Timed saves can vary by one write.

The final untraced accelerated 1000-round/221-encounter run completed in 37.44s
wall / 29.33s CPU, median round 10.50ms and p95 74.03ms. It performed 451 writes
and skipped 100 identical save requests. That run overlapped packaging; it is not
a controlled machine-wide benchmark. An earlier 1000-round allocation-traced run
also completed; tracing overhead makes its timing unsuitable for comparison.

Short packaged Chromium renderer samples, 20s each:

| Scene | Renderer Task Time | Local WS Received | Local WS Sent |
| --- | --- | --- | --- |
| Title idle | 0.0032s | 0 frames / 0 payload bytes | 1 frame / 82 bytes |
| Five-member Lab automatic combat | 2.3218s | 10 frames / 63,493 bytes | 6 frames / 575 bytes |

These are renderer task-time and payload counts, not native whole-process CPU,
WebView subprocess memory, framing overhead, hosting bandwidth, or a long soak.
Combat may complete during a sample. No production Render/Supabase calls occur.

## Outstanding Gates

- Steam account/App/Depot IDs, licensed SDK bridge decision, real Steam launch,
  overlay, optional achievements/Cloud, and verified Steam-user save isolation.
- Clean independent PC, actual Windows DPI/multiple monitors, suspend/resume,
  physical controller/Deck/Linux, update/uninstall, signing, malware validation.
  Defender status query was access-denied here; no antivirus clearance is claimed.
- Multi-hour native soak and full player-driven progression/external playtest.
- 154 game asset files remain rights/AI-status unreviewed. Installed dependency
  notices were collected, but proxy_tools has MIT metadata without a packaged
  license text, and vendored/native/runtime redistribution review remains open.
- Product icon/store art/trailer, pricing/support/legal details, owner-approved
  content disclosures, and Steam store/build reviews. No release approval claimed.

See `steam-release-gates.md` for the handoff and repeatable tools. Benchmark,
browser, native, diagnostic, and generated inventory artifacts stay in ignored
test/build directories and are not production profiles.
