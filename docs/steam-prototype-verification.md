# Desktop Prototype Verification

Date: 2026-10-25. Platform: Windows 11 x64. Scope: first offline Steam conversion milestone.

## Passed

- 48 pytest regression tests, including 17 desktop-specific tests and 31 inherited runtime tests.
- Ruff checks on the desktop runtime, launcher, new tests, and browser smoke tool.
- Git whitespace/error check.
- PyInstaller Windows one-folder/windowed build using `build_desktop.ps1`.
- Source runtime opened a native WebView2 window and shut down after its loaded event.
- Final packaged executable opened its native WebView2 window and exited successfully using an isolated test profile.
- Final packaged executable served its local game UI on loopback without an external Python interpreter being launched.
- With all non-loopback browser HTTP requests blocked: create a Black Guard, follow the tutorial to the Arena, win the introductory fight, and obtain a Rare item.
- Reload the UI, visit local Chronicle Records, return to title, and reopen the same saved character.
- Quit the packaged application, start the executable again with the same test profile, and reopen the character. Disk state retained the character, one victory, XP, and the Rare item.
- No external browser requests or JavaScript page errors during those smoke tests. Desktop logs for the final packaged gameplay/native checks were free of application errors.
- Local save tests cover corrupt-primary recovery, invalid-save refusal, future-version refusal, atomic-replace failure, bounded backups, and second-instance exclusion.
- Labyrinth regression test resumes a saved combat round with player state intact; explicitly leaving clears its checkpoint.

## Known Boundaries

- The browser blocking test is not an operating-system network isolation/firewall test. Backend cloud credentials are disabled by construction and separately tested, but a clean disconnected-machine test is still required.
- The native smoke checks window loading; the detailed gameplay checks drive the same packaged server through headless Chrome, not through native WebView input automation.
- No clean-machine install, Steamworks App ID, overlay, achievements, Steam Cloud, controller, Deck/Linux, multiplayer, store submission, asset-license audit, or signing validation is claimed.
- No full level-1-to-prestige playthrough or multi-hour soak test has been completed for this desktop branch yet.
- Test profiles, generated executables, caches, and logs are excluded from source control. Production web saves, database tables, and the live `main` deployment were not changed.

## Repeat

Run `build_desktop.ps1`. Start the executable in browser mode with a fresh test data directory and a chosen local port. Run `tools\desktop_browser_smoke.py --port <port> --output <test-directory> --quit`. Restart the executable using the same profile, then repeat the tool with `--resume-only --quit`. Use a separate profile with `--native-smoke` for the native-window startup check.
