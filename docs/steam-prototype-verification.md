# Desktop Alpha 0.2.0 Verification

Updated: 2026-10-26. Platform: Windows 11 x64. Scope: offline desktop conversion and viewport/display milestone. The earlier 0.1.0 executable is preserved in `.build-backups/steam-0.1.0-8a317ae/PrismQuest`.

## Passed

- 68 pytest regression tests, including 31 inherited runtime tests and 37 desktop/storage/display/build/transport tests.
- Ruff checks on the desktop runtime, launcher, new tests, and developer tools.
- Git whitespace/error check.
- PyInstaller Windows one-folder/windowed build using `build_desktop.ps1`.
- Source runtime opened a native WebView2 window and shut down after its loaded event.
- Final packaged executable opened its native WebView2 window and exited successfully using an isolated test profile.
- Final packaged executable served its local game UI on loopback without an external Python interpreter being launched.
- With all non-loopback browser HTTP requests blocked: create a Black Guard, follow the tutorial to the Arena, win the introductory fight, and obtain a Rare item.
- Reload the UI, visit local Chronicle Records, return to title, and reopen the same saved character.
- Quit the packaged application, start the executable again with the same test profile, and reopen the character. The final 0.2.0 cold-restart check retained the character, XP, gold, inventory, and equipment without JavaScript errors.
- No external browser requests or JavaScript page errors during those smoke tests. Desktop logs for the final packaged gameplay/native checks were free of application errors.
- Local save tests cover corrupt-primary recovery, invalid-save refusal, future-version refusal, atomic-replace failure, bounded backups, and second-instance exclusion.
- Labyrinth regression test resumes a saved combat round with player state intact; explicitly leaving clears its checkpoint.
- Actual disk round-trip with inventory items and a companion in the Labyrinth. Display-only Item objects are serialized explicitly; player inventory/equipment stay unchanged after reopening. Zero HP/mana remain zero during member normalization.
- Final packaged title, Arena, and town checks at 1280x720, 1366x768, 1920x1080, 960x600, 2560x1080, and the scaled 800x500 fallback. Window/page dimensions remained bounded and primary controls remained onscreen. Title image uses `contain` and stays inside its frame.
- Town and Arena tutorial action buttons fit inside a 960x600 client viewport.
- Final packaged Inn, Marketplace, Transmutation, Well, Glossary, local records, settings, and Labyrinth entry checks at 1280x720, 960x600, and 1920x1080. Vault actions fit at 1280x720 and 960x600; inventory actions and saved sets remain accessible in their bounded workspace.
- Inventory hover leaves the Close button's DOM identity unchanged. Closing inventory from an expedition returns to the Labyrinth without leaving it.
- Five-member Labyrinth party/map checks at 1280x720, 960x600, and 1920x1080, including party HP/mana within each card. Tank activation has the expected green outline. The map responds to ArrowRight.
- Three-monster Labyrinth encounter checks at 1280x720, 960x600, and 1920x1080; all three monster cards and their HP bars fit in the client window.
- Native hidden-window resize to 1100x720 produced a 1084x681 client viewport with content height 681, title art, and the native fullscreen control present. Display preferences saved the resized dimensions. Native process exited successfully after the idempotent transport-close fix.
- Manual save backup creation through Settings > Desktop. Unit tests also verify manual copies are not pruned with rotating backups and invalid saves are not exported as good backups.
- Windows executable product/file metadata reports 0.2.0/0.2.0.0. All 844 bundled files matched the package SHA-256 inventory after the final gameplay/native checks, with no unexpected files. A resolved Windows development lock is included.

## Known Boundaries

- The browser blocking test is not an operating-system network isolation/firewall test. Backend cloud credentials are disabled by construction and separately tested, but a clean disconnected-machine test is still required.
- The native smoke checks window loading; the detailed gameplay checks drive the same packaged server through headless Chrome, not through native WebView input automation.
- CSS client-viewport sizing and native resize were tested; real Windows display-scaling changes, multi-monitor movement, and manual fullscreen/input compatibility still require platform QA. The 800x500 fallback is not a controller/Deck certification.
- No clean-machine install, Steamworks App ID, overlay, achievements, Steam Cloud, controller, Deck/Linux, multiplayer, store submission, asset-license audit, or signing validation is claimed.
- No full level-1-to-prestige playthrough or multi-hour soak test has been completed for this desktop branch yet.
- Test profiles, generated executables, caches, and logs are excluded from source control. Production web saves, database tables, and the live `main` deployment were not changed.

## Repeat

Run `build_desktop.ps1`. Start the executable in browser mode with a fresh test data directory and a chosen local port. Run `tools\desktop_browser_smoke.py --port <port> --output <test-directory> --quit`. Restart the executable using the same profile, then repeat the tool with `--resume-only --quit`. Use a separate profile with `--native-smoke` for the native-window startup check.

Use `tools/desktop_layout_smoke.py` with a fresh profile for the viewport/tutorial checks. Create a separate disposable profile using `tools/seed_desktop_profile.py .local-test/<name>` and run `tools/desktop_advanced_smoke.py` against that profile for services, items, and party checks. Fixtures are restricted to `.local-test` and never replace an existing save. Do not use `--live-css` for release verification; final packaged checks used only bundled presentation assets.
