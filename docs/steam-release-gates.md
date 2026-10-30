# Release Gates and Owner Handoff

This is a Windows alpha with offline play and an opt-in network preview, not a
Steam-ready or legally cleared release. See `concourse-network-0.10.md` for the
playable test realm and the explicit hosting/Steam authentication release gates.

## Account and Platform

- Complete Steamworks partner/business/tax setup; create PrismQuest's own App ID
  and Windows Depot ID. Do not send passwords/tokens in chat or commit them.
- Decide optional Steam achievements/Cloud scope and select a maintained licensed
  SDK bridge with the current SDK. No borrowed test App ID or unlicensed SDK DLL
  is bundled. Steam distribution does not itself require achievements.
- Early gate: install/launch through the real Steam client and test Overlay with
  the WebView renderer. If incompatible, decide limited integration vs renderer
  change before promising overlay-related features.
- Current default saves belong to the Windows profile, not a verified Steam user.
  Add verified Steam-user profile isolation before enabling Steam Cloud or claiming
  safe sharing between multiple Steam accounts on one Windows login. Never trust
  a user-supplied Steam ID as authentication.
- Cloud configuration should sync only versioned game-save documents, not browser
  caches, logs, locks, secrets, or all backup files. Test cross-device/older-version
  conflict handling before enabling it. External replacement detection is a local
  guard, not a complete Steam Cloud conflict implementation.

## Prepared Upload Tooling

After `build_desktop.ps1`, run `tools/prepare_steampipe.py --app-id YOUR_APP_ID
--depot-id YOUR_DEPOT_ID`. It verifies the package and writes VDF files in ignored
`build/steampipe`. IDs are mandatory. The scripts have Preview=1, no SetLive,
and no credentials. They do not invoke SteamCMD or upload anything.

In Steamworks, configure the Windows launch executable as `PrismQuest.exe`, with
the full folder as depot content. Configure/install WebView2 using an approved
Microsoft redistribution approach and test on a machine missing it. The current
build detects a missing runtime and explains how to install it; no installer is
bundled or downloaded automatically.

Use an internal beta branch and access controls first. Inspect SteamPipe preview,
upload through your own authenticated SDK tools, test download/update/rollback,
and only then consider a public branch. Keep a complete prior depot build and a
separate prior-format save backup; an old executable may not read a newer save.

## Rights and Store

`dist/PrismQuest/THIRD_PARTY_NOTICES.md`, `third-party-inventory.json`, and
`asset-rights-review.csv` are generated inventories, not rights approval.
The inventory includes build/test dependencies as well as runtime packages.
Review all native/Python runtime notices, vendored NiceGUI JS/fonts/icons,
Microsoft components, and any metadata/license gaps. Art files are explicitly
unreviewed; only the owner can confirm source/ownership and AI usage/disclosures.
Retain the actual applicable notices in the final shipping package.

Provide product icon/branding, capsule/library images, screenshots, trailer,
price, support contact, store copy, privacy/legal material, supported languages,
minimum/recommended hardware based on measurements, and accurate content/AI
questionnaire answers. Avoid unsupported controller, multiplayer, Deck, Cloud,
achievement, OS, or accessibility claims. Complete store and build reviews.

## Compatibility and Candidate QA

- Fresh Windows install without Python/dev tools; no internet after prerequisites.
- Read-only install folder, non-ASCII Windows username, low disk space, antivirus.
- Real 125/150/200% DPI, multiple monitors, fullscreen, alt-tab, suspend/resume.
- New install, update over old build, uninstall/reinstall without deleting saves.
- Full player-driven level-1-to-prestige and endgame sessions, multiple classes.
- Multi-hour native soak; record process/WebView memory, CPU, frame/input response,
  local socket bytes, save latency, errors, and recovery behavior.
- External playtest and final licensed-asset review. Physical controller and
  Deck/Linux testing are separate optional scope, not completed by browser tests.

## Primary References

- Steam release: https://partner.steamgames.com/doc/store/releasing
- SteamPipe: https://partner.steamgames.com/doc/sdk/uploading
- Overlay: https://partner.steamgames.com/doc/features/overlay
- Cloud: https://partner.steamgames.com/doc/features/cloud
- WebView2 deployment: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
- Testing guidance: https://github.com/affaan-m/everything-claude-code/tree/main/rules
