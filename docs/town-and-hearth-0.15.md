# The Town and the Hearth / 0.15.0

## Design and Rules

The Inn foregrounds the recovery decision, not a paragraph of service exposition.
Capacity-based recovery is shown as a solid current meter plus a quiet forecast
hatch. Price, retained gold and the Monster Chain reset are visible together.
Nonzero chains require explicit inline confirmation. Fully recovered/no-chain
heroes cannot waste a room payment. Original class fee, 35% recovery/minimums,
Vault capacity pricing and free deposits/withdrawals remain unchanged.

The artwork stays contained, with a static warm halo. Vault and pack are equal
preparation tiles; recovery and the next Arena action remain pinned. The saved
receipt reports actual health/mana gained, not a promised full heal. Its finite
local motion respects reduced motion and does not slow gameplay or add polling.

Town Crier's session-only map now belongs to each chronicle. It is normalized,
validated and saved along with the service payment; failed actions restore the
same spending totals. Slot switching cannot bleed counts across modes or add
them a second time. Earlier unsaved spending cannot be reconstructed. Paid
charters count; free feeder rooms do not.
Local charters and escrow are retained with recorded spending across a local
season reset too, so it cannot strand another chronicle's guild membership or
silently erase an item held by the new town service.

## Community Scope

Concourse is removed from main navigation and no longer initialized by the
launcher. Its developer service/test data remain preserved. The direct Bazaar,
Guild Hall and Realm Ladder use the current chronicle rather than a cloned test
character. With no Steam App ID/backend configured, these are deliberately local
services, not a claim of live multiplayer or Steam connectivity.

Bazaar is a click-pinned shelf and item sheet. Search, tier, type, rarity, affix
and sort apply to Browse and Sell & Manage. Price drafts are not refreshed while
typing. Review locks the exact item/price; stale callbacks from discarded inputs
cannot replace an approved draft. Listing consumes one exact object reference
from the pack, preserving distinct equal-valued items. Escrow is an owned item
location, ledger entries are not. Reprice is version-checked; cancellation returns
the item once. The transaction model also tests same-mode local purchase with
both payments and delivery committed together. The normal three-chronicle profile
has one chronicle per mode, so its Browse shelf can truthfully remain empty; it
does not invent counterparties or mix Core, HC and SSF. No listing is sent online.

Guild Hall presents a deliberate charter or an established hall: a quiet code-native
crest, genuine member roll and private local board. It retains the main-game
1,000g charter fee (the removed sandbox had waived it). Charter review is explicit;
joining is free. Local codes only work in this profile. Founder-leave restrictions
are preserved. Messages are rendered as text, not HTML, with no background chat
timer or input re-render. No synthetic guildmates or conversation is generated.

Realm Ladder shows only actual saved chronicles and recorded PQ attempts. It
offers mode filters, highest-level/win/time sorting and a separate My Ascents
history. The current hero's next action remains pinned, including compact windows.
It does not alter ladder stats, initiate seasonal resets, upload saves or create
a pretend global rank. Live shared economy/Steam features still require native
authentication and an authoritative hosted backend; local files remain untrusted
for that purpose.

## Persistence and Recovery

Economy changes use the existing staged desktop transaction boundary. Local
escrow and both sides of a trade live in the same atomic chronicle document,
not a second database that could commit only half a transfer. Failed saves
restore player, slots, coffer totals and related state. IDs/revisions distinguish
listings; object identity/fingerprints distinguish pack items. An alive hero's
carryover mirror is validated but not counted as a second owned inventory.

Format 3 is intentional: older normalizers do not understand this escrow location.
They must reject the save instead of silently discarding listings. Existing
format-1/2 documents load without losing fields and upgrade on the next save.
A deterministic, non-rotating `before-format-3-from-*` copy is kept before upgrade,
in addition to the existing rotating backups. Retrying a failed upgrade reuses
the same matching copy rather than filling storage with duplicate backups.

The complete 0.14 executable is preserved in
`.build-backups/reimagined-0.14.0-fa5fc87/PrismQuest`. Source predecessor is
`fa5fc87`. Rollback requires the matching pre-format-3 save, not merely swapping
the executable. Normal AppData saves are never used for QA.

## Verification

Tests follow the ECC red-first regression workflow, with offline unit/integration
checks and real Chrome/native-window checks. No measured coverage percentage or
production load benchmark is claimed. Tests cover Crier restart/slot isolation,
original recovery forecasts, failed rest rollback, exact-item escrow, bounded
prices, stale revisions, two-sided payment rollback, guild membership, cold save
round trips and retained format-upgrade backups. Source browser acceptance has
passed 45 viewport checks over 800x500, 960x600, 1280x720 and 1920x1080, with actual
rest/list/reprice/return/charter/message operations and item conservation. The
normal-flow fixture recorded exactly 1,015g (three Warlock rooms and one charter),
with no page errors or unintended external requests.

Scroll/focus preservation is local and bounded; arrow keys move through the
Bazaar shelf without moving the page. Long lists and history scroll within their
panes. Inspection remains Ctrl-hover/Ctrl-focus. The shared CSS cascade was
corrected so primary buttons and selected cards/tabs retain their intended visual
hierarchy instead of being flattened by the base Quasar/Nocturne layer.

The final Windows package passed the same 45 town viewport checks, then a cold
process restart preserving the 1,015g total, escrow history and guild board.
All 364 automated tests and lint checks passed. Native WebView2 startup reported
1084x681 content fitting its 681px client height. The packaged Marketplace/PQ
chapter regression passed too, as did Arena arrival/results and last-drop
inspection during real combat. Ctrl-hover now ignores modifier-less hover events
generated by DOM replacement; key release, actual pointer movement and window
blur still close inspection correctly. Service receipts/reviews do not leak
between Bazaar, Guild Hall and Ladder.

Both the new build and preserved 0.14 build passed their 1,006-file integrity
checks. The actual 0.14 executable rejected a disposable format-3 save without
changing its bytes. No normal player profile or hosted deployment was used.
These are functional/layout checks, not Steam multiplayer certification or a
claim of production-scale load performance. Existing release/license audit gates
remain in force.
