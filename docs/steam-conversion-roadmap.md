# Steam Conversion: Implementation Track

## Boundary and Decisions

- Source baseline: hosted `main` commit `10347d7b72ebbb81fa5a7ade44dd3391c7c284d4`.
- Work branch: `codex/steam-standalone`, in a separate `SteamEdition` Git worktree.
- First platform: Windows x64, offline-first, retaining the Python game and visual design.
- First delivery: a runnable native-window prototype, not a storefront-ready product.
- Hosted saves, ladder, accounts, and database schema stay untouched.
- No Steam App ID is invented or borrowed, and no production credentials are bundled.
- A WebView wrapper is a migration bridge, not proof that Steam Overlay or controller support will work. Those are explicit technical validation gates.

## Milestone 1: Local Playable Foundation

Implemented in this branch:

1. A separate desktop launcher, runtime package, pinned desktop requirements, Windows build script, and PyInstaller specification.
2. Loopback-only game hosting in a native Edge WebView2 window, with packaged Python and bundled game assets.
3. Offline local chronicles in a writable user profile, separated from installed program files.
4. Atomic save writes, checksums, bounded recovery copies, fail-safe handling of damaged saves, and a single-writer profile lock.
5. Solo Labyrinth expedition checkpoints with companions, party state, votes, reward acknowledgements, and explicit-leave cleanup.
6. Desktop-aware menus: no cloud login requirement, online-only scenes unavailable, local progression records, and an explicit Quit action.
7. Desktop diagnostics and tests for paths, saves, recovery, title-screen navigation, and Labyrinth restoration, alongside existing game regression tests.

This milestone preserves existing combat and progression rules rather than attempting a risky simultaneous game-engine rewrite. The large legacy module remains behind a desktop runtime boundary and is still technical debt.

## Milestone 2: Architecture and Economy

1. Separate pure game models, random rolls, combat resolution, item ownership, progression, and saves from NiceGUI rendering and cloud functions.
2. Add typed adapters for storage, identity, achievements, notifications, and optional networking. Steam and browser implementations must not share credentials or writable economy state by accident.
3. Define the standalone progression/season experience: manual fresh runs, rotation schedule, local records, prestige, endgame, and treatment of missed calendar seasons.
4. Audit every online-only reference and explain unavailable features honestly. Decide whether an offline NPC system replaces the player Bazaar or the existing Marketplace is sufficient.
5. Version save migrations and run migrations against real anonymized fixtures. Handle future-version saves by refusing to downgrade them, not by silently loading an older backup.
6. Expand transaction/idempotency tests across drops, inventory, saved sets, vault, companions, transmutation, and quit/reload at each ownership transition.

Exit gate: the full offline progression loop is independently playable, testable, and cannot silently duplicate or delete player-owned items during save/load.

## Milestone 3: Desktop Experience

1. Test layouts at 1280x720, 1366x768, 1920x1080, ultrawide, and 125-200% Windows scaling. Fix clipping and nested scrolling across every scene and modal.
2. Add window/fullscreen settings, remembered window geometry, keyboard navigation, focus indicators, rebindable controls, accessible text/motion settings, and a reliable pause/quit flow.
3. Decide controller support. Implement all essential inventory, combat, Labyrinth, menus, and text-input flows before claiming controller compatibility.
4. Establish audio, master/music/effects levels, feedback consistency, loading state, and recovery UI instead of opaque white screens.
5. Test suspend/resume, alt-tab, monitor changes, offline launch, non-ASCII Windows usernames, read-only install directories, and missing WebView2.
6. Measure idle CPU, peak combat CPU, frame responsiveness, local socket traffic, memory growth, and save/checkpoint cost during long sessions. Profile before optimizing, and keep graphics reduction separate from combat pacing.

Exit gate: no critical layout, input, save, or performance regressions during multi-hour testing.

## Milestone 4: Steamworks Proof of Concept

Owner inputs: Steamworks partner access, the game's own App ID, current SDK access, business/tax setup, and decisions about price and online scope. Never store partner secrets or signing keys in Git.

1. Test a licensed, maintained Python/native Steamworks bridge in the packaged build, including initialization, callbacks, shutdown, DLL placement, and launch from Steam.
2. Validate Overlay behavior with the actual WebView renderer. If it cannot meet requirements, decide between a documented limited integration and a renderer/client migration before investing in deep UI work.
3. Add achievements/stats with offline event buffering and idempotent unlocks. Define behavior for manually edited local saves.
4. Configure Steam Cloud for versioned save documents only, and build conflict resolution, recovery, quota handling, and cross-device migration tests. Cloud sync is not equivalent to the game's former Supabase account system.
5. Preserve offline launch and avoid requiring a second login for the solo experience.
6. Implement Steam language/launch options and crash diagnostics consistent with user privacy and the store description.

Exit gate: a packaged build launched through the real Steam application passes integration checks. Browser appearance alone is not sufficient.

## Milestone 5: Optional Online Features

1. Decide whether multiplayer Labyrinth is required for launch or a later update. Offline-only saves cannot become trusted public multiplayer/economy state by default.
2. If online is retained, implement server-validated Steam identity and an authoritative run/economy service with atomic ownership transactions, replay protection, bounded reconnect windows, and schema migrations.
3. Add lobby, invite, reconnect, host-disconnect, and mixed-version behavior. Do not expose the local NiceGUI server to the public internet as a multiplayer implementation.
4. Design abuse prevention, moderation/reporting, privacy/data retention, server budgets, and shutdown/failure behavior before restoring shared trading or public ladders.
5. Load-test five-player combat, reconnect storms, and latency/loss cases against actual deployment limits.

Exit gate: online functionality has a tested trust model and does not corrupt local or hosted production characters.

## Milestone 6: Packaging and Release

1. Reproduce builds on a clean Windows machine with a complete dependency lock, software inventory, license notices, malware scans, and build hashes. Exclude dev tools, credentials, and test profiles.
2. Audit ownership/licenses for all art, fonts, audio, dependencies, and any generative-AI content; complete current Valve disclosures and content questionnaires accurately.
3. Set product name, icon, executable metadata, supported OS/hardware, save location, WebView2 prerequisite strategy, and optionally code-sign binaries.
4. Configure Steam depots/branches, launch executable, install prerequisites, access control, and a tested rollback build. Store credentials in appropriate secret storage only.
5. Prepare capsule art, screenshots, trailer, store copy, support contact, accessibility/controller claims, privacy information, and any required legal notices. Verify current Steamworks requirements before submission.
6. Run internal alpha, external playtest, and candidate builds. Test new install, update over old install, uninstall/reinstall without losing saves, Steam Cloud conflicts, and fallback recovery.
7. Submit store and build review with enough time to address feedback. Release only after the technical and storefront gates are met.

## Immediate Next Development Slice

Playtest the offline prototype end-to-end, then extract item ownership and save migrations before adding Steam SDK features. Decide whether release 1.0 must include multiplayer; this is the largest remaining scope and security decision.

## Primary Technical References

- NiceGUI deployment/native mode: https://nicegui.io/documentation/section_configuration_deployment
- PyInstaller runtime paths: https://pyinstaller.org/en/stable/runtime-information.html
- PyInstaller multiprocessing caveats: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- pywebview engines: https://pywebview.flowrl.com/guide/web_engine
- Steamworks documentation: https://partner.steamgames.com/doc/home
- Steam Overlay: https://partner.steamgames.com/doc/features/overlay
- Steam Cloud: https://partner.steamgames.com/doc/features/cloud
