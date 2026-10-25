# PrismQuest: Standalone Desktop Prototype

This is the first Windows/offline milestone of the Steam conversion. It is not a Steam release yet. Development is isolated on `codex/steam-standalone`, based on web release `10347d7`. Do not merge or deploy this branch over the hosted web game.

## Play the Windows Build

Open `dist\PrismQuest\PrismQuest.exe`. Keep the whole `PrismQuest` folder, including `_internal`; the executable is not a single-file distribution. Python is bundled and is not required on the player's machine. Windows and Microsoft's Edge WebView2 Evergreen Runtime are required. A clean-machine prerequisite/install test is still outstanding.

The default launch opens a native desktop window and a loopback-only local game server. It does not connect to Render or Supabase. An internet connection or web account is not required for the core game.

Three local chronicles support the existing Arena, Well, Marketplace, inventory, saved sets, vault, transmutation, Prismatic Quest progression, solo Labyrinth, and companion systems. Local Labyrinth checkpoints are stored with the chronicle and resume when that slot is reopened. Explicitly leaving an expedition clears its checkpoint.

Online Bazaar, direct vault courier, guilds, shared ladder, multiplayer matchmaking, cloud saves, Steam achievements, Steam Cloud, and Steam overlay integration are not available in this prototype. Local Chronicle Records replace the global ladder. Social links can still open external websites when deliberately clicked. Locally editable characters must never be uploaded into the existing trusted online economy without a separate security design.

## Local Data

The default Windows profile is `%LOCALAPPDATA%\PrismQuest\SteamEdition`:

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
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
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

```powershell
& .\.venv\Scripts\python.exe -m pytest tests -q
& .\build_desktop.ps1
```

The build uses PyInstaller in one-folder/windowed mode. Top-level dependencies are pinned; a fully transitive, independently reproduced release lock and supply-chain audit remain release tasks. Native mode uses `multiprocessing.freeze_support()` before GUI imports, which is required for packaged Windows child processes.

`tools\desktop_browser_smoke.py` drives a fresh profile on a running browser-mode server, blocking all non-loopback HTTP requests. It checks character creation, the introductory Arena fight, a guaranteed Rare item, browser reload, local records, and title-screen reopening. Use `--resume-only` after restarting the application with that profile to check disk persistence, and `--quit` to exit cleanly. It currently uses a locally installed Chrome; it is a developer test, not a runtime dependency. `--native-smoke` is a hidden developer check that creates a hidden WebView2 window, records `native-smoke.ok` in its test profile, and exits.

See `docs\steam-prototype-verification.md` for validation results and `docs\steam-conversion-roadmap.md` for the remaining conversion milestones and release gates.
