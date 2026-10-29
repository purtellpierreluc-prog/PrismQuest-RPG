# PrismQuest Reimagined 0.5.0

This is an experience-design fork of the Windows/offline Steam conversion, isolated on `codex/steam-experience-redesign`. It is not a Steam release yet. Nocturne 0.4.0 remains in `SteamEditionVisual`, with rollback tag `steam-nocturne-v0.4.0` at `af00de2`. The original 0.3.0 edition remains in `SteamEdition`. Neither preserved executable nor the hosted web game is replaced.

Reimagined changes the information architecture, not just the skin: a battle-first Arena with live rounds and a dedicated reward phase, contextual town goals, an equipment workbench with real recalculated stat trade-offs, click-locked selection, a separate character-build workspace, global navigation, and expedition objectives. Artwork, combat rolls, item ownership, economy and save-format rules are preserved. See `docs/experience-redesign.md` for design, verification and rollback notes.

Screenshots of the new decision loop are included in `docs/experience-redesign.md`.

## Play the Windows Build

Open `dist\PrismQuest\PrismQuest.exe`. Keep the whole `PrismQuest` folder, including `_internal`; the executable is not a single-file distribution. Python is bundled and is not required on the player's machine. Windows and Microsoft's Edge WebView2 Evergreen Runtime are required. A clean-machine prerequisite/install test is still outstanding.

The 0.1.0 executable folder was preserved in `.build-backups\steam-0.1.0-8a317ae\PrismQuest` before rebuilding 0.2.0. This is a local rollback copy, not part of the Git repository.

The verified 0.2.0 executable is also preserved in `.build-backups\steam-0.2.0-c180079\PrismQuest`, with Git rollback tag `steam-alpha-v0.2.0`. Format-2 saves require 0.3.0 or later; use the preserved older save backup when reverting the executable.

## Release Hardening

Desktop item mutations now stage changes and commit once; failure restores prior items/gold in memory. Transmutation rolls its result before consuming offerings, and companion equipment no longer deletes distinct saved items with identical stats. Tank updates preserve party order even when join timestamps tie.

Save format 2 validates item/economy containers, reads format 1 losslessly, preserves the previous file in backups on upgrade, skips unchanged snapshots, and refuses to overwrite externally replaced/deleted saves. Native UI reloads share one live state instead of creating a second stale character writer. Final-class prestige records completion without resetting other local chronicles or erasing the current hero. There are no automatic server/calendar resets; local NPC Marketplace remains the trading alternative.

Settings > Desktop adds reduced decorative motion and privacy-limited diagnostic export. The launcher checks WebView2 before opening a native window. `--diagnostics` writes a local report without starting gameplay, and `--verify-package` checks installed file hashes. These features do not upload telemetry or configure Steam Cloud.

## Display and Recovery Controls

The desktop uses a window-sized workspace rather than a vertically scrolling web page. Arena, town, and active Labyrinth layouts keep their primary controls visible. Long inventories, saved sets, references, and companion-management drawers scroll inside bounded panels. Title artwork uses a contained image rather than a cropped cover image.

The native window has a 1000x660 minimum outer size. Layout checks include 960x600 client viewports, 720p, laptop, Full HD, and ultrawide sizes. Smaller/DPI-constrained viewports use a resize-event-only scale fallback; this is not a claim of Steam Deck or controller support.

In town, open Settings > Desktop to toggle fullscreen, create a manual save backup, or open the save folder. F11 also toggles native fullscreen. Window size/fullscreen preferences are saved in `display.json`, independently of character saves. Manual backups use `manual-*.json` names and are not removed by the rotating-backup cleanup.

The default launch opens a native desktop window and a loopback-only local game server. It does not connect to Render or Supabase. An internet connection or web account is not required for the core game.

Three local chronicles support the existing Arena, Well, Marketplace, inventory, saved sets, vault, transmutation, Prismatic Quest progression, solo Labyrinth, and companion systems. Local Labyrinth checkpoints are stored with the chronicle and resume when that slot is reopened. Explicitly leaving an expedition clears its checkpoint.

Online Bazaar, direct vault courier, guilds, shared ladder, multiplayer matchmaking, cloud saves, Steam achievements, Steam Cloud, and Steam overlay integration are not available in this prototype. Local Chronicle Records replace the global ladder. Social links can still open external websites when deliberately clicked. Locally editable characters must never be uploaded into the existing trusted online economy without a separate security design.

## Local Data

The default Windows profile is `%LOCALAPPDATA%\PrismQuest\SteamEditionReimagined`. It deliberately does not open or modify either preserved edition's profile:

- `saves\chronicles.json`: the three local slots, including solo Labyrinth checkpoints.
- `backups\chronicles-*.json`: ten previous valid save revisions.
- `backups\unreadable-*.json`: preserved unreadable saves, if recovery was needed.
- `logs\desktop.log`: rotating diagnostic log; `startup-error.log` records startup failures.
- `browser\`, `ui\`, and `cache\`: desktop browser preferences and disposable presentation data.
- `session.key`: a local UI session secret, not a Steam/API credential.

Writes use a same-directory temporary file, flush/fsync, and atomic replace. A checksum detects corruption, not cheating. A valid backup is loaded if the primary is damaged. If all existing saves are invalid, startup stops rather than resetting progress. Saves from a newer game version are never silently downgraded to an older backup. A per-profile process lock prevents two game instances writing the same saves simultaneously.

Game updates must not replace or remove this profile. Steam Cloud should eventually sync game saves only, not browser caches, locks, logs, or secrets. Keep a separate manual backup before testing new builds.

## Develop

Use Python 3.12 on Windows:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows-dev.lock.txt
& .\.venv\Scripts\python.exe launch_desktop.py
```

Test in a separate local profile without touching normal saves:

```powershell
& .\.venv\Scripts\python.exe launch_desktop.py --data-dir .local-test\manual
```

For local browser diagnostics only:

```powershell
& .\.venv\Scripts\python.exe launch_desktop.py --browser --port 8097 --data-dir .local-test\browser
```

`--browser` still runs entirely locally. Do not change the loopback binding to a public address. The `--data-dir` directory must not be shared by concurrent instances.

## Verify and Package

For this redesigned interface, use `tools/desktop_experience_smoke.py --port PORT --output .local-test/NAME` against a fresh disposable profile. Add `--seeded` for a profile created by `tools/seed_desktop_profile.py`. Earlier browser/layout drivers below document the older editions' interfaces and are not the current UI acceptance driver.

```powershell
& .\.venv\Scripts\python.exe -m pytest tests -q
& .\build_desktop.ps1
```

The build uses PyInstaller in one-folder/windowed mode. `requirements-windows-dev.lock.txt` records the resolved Windows/Python 3.12 build environment; clean-machine reproduction and the supply-chain/license audit remain release gates. The executable contains Windows product/version metadata. `build-info.json` records the build environment and SHA-256 hashes of bundled files; it is an integrity inventory, not code signing. Native mode uses `multiprocessing.freeze_support()` before GUI imports, which is required for packaged Windows child processes.

`tools\desktop_browser_smoke.py` drives a fresh profile on a running browser-mode server, blocking all non-loopback HTTP requests. It checks character creation, the introductory Arena fight, a guaranteed Rare item, browser reload, local records, and title-screen reopening. Use `--resume-only` after restarting the application with that profile to check disk persistence, and `--quit` to exit cleanly. It currently uses a locally installed Chrome; it is a developer test, not a runtime dependency. `--native-smoke` is a hidden developer check that creates a hidden WebView2 window, records `native-smoke.ok` in its test profile, and exits.

See `docs/experience-redesign.md` for this fork's validation and `docs\steam-conversion-roadmap.md` for remaining Steam release gates. Nocturne's earlier evidence remains in `docs/nocturne-visual-edition.md`.

See `docs/desktop-player-guide.md` for controls/recovery and `docs/steam-release-gates.md` for the owner/platform handoff. Builds generate third-party notices and a 154-file asset-rights inventory; rights remain unapproved until reviewed. `tools/prepare_steampipe.py` requires real App/Depot IDs and generates preview-only VDF files, never an upload or automatic live deployment.

`tools/desktop_benchmark.py` runs accelerated backend rounds in a fresh disposable profile; `--trace-memory` enables expensive allocation tracing. `tools/desktop_performance_smoke.py` records short renderer/local-WebSocket samples against a seeded profile. Neither is a substitute for a multi-hour native soak or a full player-driven progression playtest.

`tools\desktop_layout_smoke.py` checks viewport fit and primary controls across several resolutions. `tools\seed_desktop_profile.py` creates disposable level-45 test fixtures only under `.local-test` and refuses to overwrite existing saves. `tools\desktop_advanced_smoke.py` exercises service panes, inventory/vault/saved sets, a five-member Labyrinth, tank toggling, and keyboard movement. None of these tools accesses the normal player profile.
