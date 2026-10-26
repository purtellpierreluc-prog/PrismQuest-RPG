# Desktop Release Hardening

Started: 2026-10-26. Baseline: `c180079`, rollback tag `steam-alpha-v0.2.0`.

Scope is Windows x64, offline solo with companions. No production web changes,
Steam account purchases, partner uploads, secrets, or claims of controller support.

## Local Implementation

1. Extract save validation/migration and a transactional item-operation boundary.
   Test failure before commit, failed disk writes, ownership conservation, and
   interrupted/repeated operations. Never deduplicate items merely by equal stats.
2. Detect external save replacement, avoid redundant disk writes, retain valid
   recovery copies, and expose recovery status. Test migration of previous saves.
3. Prevent web-era global season resets from wiping independent local chronicles.
   Exercise progression, prestige carryover, all classes, and multi-member combat.
4. Add local diagnostics, process/save performance measurements, and repeatable
   extended tests. Separate accelerated simulation from real-time soak evidence.
5. Add native prerequisite checks, safe diagnostics export, and desktop keyboard /
   reduced-motion polish without changing combat mechanics or pacing.
6. Prepare validated SteamPipe configuration generation, dependency/asset inventory,
   third-party notices, package verification, and a release checklist. Fail closed
   for missing IDs and unresolved release gates; never upload automatically.
7. Rebuild, verify packaged/native/browser flows, document exact evidence, commit,
   and push only `codex/steam-standalone` plus the rollback bookmark.

## External Gates

- Owner's Steamworks onboarding, App/Depot IDs, current licensed SDK/bridge choice,
  and Steam client launch/overlay verification.
- Owner confirmation of asset rights and AI/content disclosures, store price,
  final branding, marketing media, and support/legal information.
- Clean independent Windows machine, real display scaling/multiple monitors,
  suspend/resume, physical controllers, and optional Deck/Linux QA.
- Multi-hour real-time soak and external playtesting. Automated simulations and
  this development machine do not substitute for these.
- Multiplayer/trading/public ladders are excluded from the offline alpha; restoring
  them requires a separate authoritative online design, not exposing localhost.

Testing approach follows the Everything Claude Code common/Python testing guidance:
regressions first, pytest unit/integration checks, then packaged critical-flow tests.
No full-legacy-module coverage percentage or storefront-ready status is implied.

## Outcome

The locally implementable hardening slice is complete in alpha 0.3.0. See
`steam-alpha-0.3-verification.md` for exact tests/measurements and limitations.
The large legacy module is not fully extracted/replaced. Native whole-process
performance, multi-hour soak, hardware compatibility, asset/legal clearance, and
real Steam integration remain gates, not work claimed complete by these tools.
