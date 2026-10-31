# The Build and the Deep / 0.14.0

## Rules Before Ornament

Audited six proficiency families, successful-hit training, caster mana fallback,
rollover thresholds, serialization and Labyrinth actor rebuilding. Existing
damage power is preserved: the raw item multiplier is
`1 + 0.625 * item_EE + 0.01 * family_level`, before core-stat scaling and defense.
The old Enhanced Effect label was inaccurate; making proficiency count as item
EE instead would silently change balance. Affixes, armor and mana cost do not
receive proficiency scaling.

Fixed independently missing legacy progress keys without resetting supplied
levels/progress. Fixed proficiency leveling recalculating a Lab actor mid-action
and erasing temporary bonuses. The next actor rebuild applies the newly earned
level with its effects once. Existing training rates and thresholds remain.

Core and derived stat inspection uses the existing body-level tooltip portal.
The four one-point forecasts recalculate a copied build but do not copy the
inventory, use random numbers, spend points or save. Tall hovers can sit beside
their anchor; scrolling the underlying list dismisses stale inspection rather
than leaving a tooltip across another row. Tooltip scrolling remains available.
DEX grants initiative, not shorter rounds or extra actions.

## Interaction and the Well

Fixed-geometry action buttons have a quiet bevel, immediate inset pressure,
155ms content-only release, a keyboard focus ring and static disabled state.
Selectable cards and aria-pressed toggles retain their own language. Feedback
does not synthesize clicks, wait before actions, add sound voices, or send
animation frames over the socket. Reduced motion suppresses release motion.

The Well's pack shelf, ritual altar and answer form a bounded workspace. Filter
inputs remain mounted while the shelf changes. Selection uses exact object
ownership, stable tooltip keys, remembered shelf scroll and arrow-key focus.
Nothing is preselected. Review states the actual item and irreversible fee.
Primary controls stay pinned; long lists/terms/affixes scroll within their panel.

Original mechanics remain authoritative: 10g plus one Common pack item at an
eligible tier, original stronger Wellspawn fight, fixed 50% return on victory,
same type/tier, normal Magic Find rarity and advantageous affixes. No guaranteed
upgrade, extra claim, new gold payout or economy change is introduced.

Entry prepares the original encounter and commits once before combat. Failure
restores the staged item, gold, town spending and encounter data. After committed
entry, an animation/view/combat exception never refunds an already consumed
offering. An interrupted foe can continue while the same process remains open.

Victory, defeat and withdrawal stage original settlement with view callbacks
deferred. A failed disk write holds the already-rolled post-state; retries save
that exact answer, not a new roll. Receipt publication follows durable save.
Retry cannot add a second item or another kill/XP award. Hardcore cleanup stays
authoritative. These in-memory recovery stages are not crash/restart recovery:
finish retrying before quitting. A hard process loss during an unfinished fight
retains the charged entry, not a newly introduced encounter checkpoint.

Reveals wait 450ms, then use finite opacity/transform effects with elapsed-time
continuity across replaced DOM nodes. They skip on Escape, Reveal now, reduced
motion or losing focus, and do not replay when revisiting a completed answer.
Existing loot sound handles actual finds; no duplicate chime is added.

## Verification and Rollback

Tests follow the ECC testing workflow: regressions were reproduced before fixes,
then exercised with offline unit tests and real browser playthroughs. No claim
of a measured coverage percentage is made. Full regression suite: 326 tests passed.
Focused cases include all six families, partial saves, rollover, Lab modifiers,
pure forecasts, exact-item entry, stale review, repeated failed outcome writes,
cancellation, defeat, withdrawal, Hardcore cleanup and other-chronicle isolation.

Browser/build verification evidence is retained in disposable `.local-test`
profiles. Four viewport sizes cover 800x500, 960x600, 1280x720 and 1920x1080.
Only those fixtures use an overpowered hero to complete real Well battles
quickly; no test mode, reward oracle or overpowered defaults are shipped.

Packaged acceptance passed four real Well encounters (three item returns and one
miss), exact payment/inventory counts, other-chronicle preservation, first-row
selection, keyboard traversal, scroll retention and hover forecasts. A separate
reduced-motion playthrough passed two encounters. DOM-only presentation fixtures
check native Enter/Space click semantics, fixed button bounds, disabled styling
and reveal continuity after replacing its node. They do not simulate rewards.
No page errors or unintended external requests were observed in these tests.
Normal Arena onboarding/combat/last-drop inspection and Marketplace plus blind
Prismatic Quest settlement/carryover also passed on the packaged build. Native
WebView2 launch/resize passed at 1084x681 client size with no page overflow.
Package integrity checked 1,006 files with no changed or unexpected files.

Previous source: `steam-reimagined-v0.13.0` / `a24328c`. Complete prior executable:
`.build-backups/reimagined-0.13.0-a24328c/PrismQuest`. Do not roll back saves by
copying test profiles. Normal AppData saves, web/main, SteamEdition and
SteamEditionVisual were not used for testing or replaced.
