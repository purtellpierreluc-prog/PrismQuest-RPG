# The Crucible / Reimagined 0.11.0

## The Design

Transmutation is a deliberate gamble, not a guaranteed upgrade. The interface
separates three jobs instead of squeezing a dialogue, two dropdowns, forecasts
and a giant reveal into competing scrolling cards:

1. **Your Offerings:** searchable pack shelf, tier/rarity filters, type-colored
   edges and rarity-tinted surfaces. Choose a form first; the shelf then shows
   same-tier sacrifices. Hover for full item stats. Arrow keys move focus,
   Enter/Space select. Browsing and selection preserve the shelf's scroll.
2. **The Ritual:** distinct Form and Sacrifice slots, visible fee and remaining
   gold, then an inline confirmation naming both consumed items. Nothing is
   preselected. Changing either offering invalidates confirmation.
3. **The Possibilities:** guaranteed type/tier, actual rarity probabilities,
   and clear disclosure that affixes reroll and power can decrease. Identical
   rarity outcomes are combined, e.g. Fine + Rare gives 85% Rare / 15% Fine.

After a successful, durable transaction, the existing sanctum art, brass orbits,
bounded convergence, rarity wash, one shimmer and staggered affixes present the
item. It is already in the pack; there is no second claim step or hidden reward
transaction. The shelf temporarily conceals the newly forged item so it cannot
spoil the reveal. Skip with the on-screen control or Escape. Reduced-motion and
disabled item-animation settings show the result immediately. Quiet reward
audio respects the existing effects/reward/mute/focus controls.

**Inspect in Inventory** opens the exact result if still owned. **Use as Next
Form** supports repeat crafting without selecting an unreviewed sacrifice.
**Last Result** is a read-only session record, not another owned copy. It stays
available between scene visits but never replays its reveal or sound on return.

## Rules and Safety

The original `transmute_selected` transaction still owns all randomness, gold,
town spending, two-input removal, result creation and atomic saving. No drop,
affix, rarity or cost tables changed:

- Fine-or-better, two different pack items of the same required tier.
- Output retains the first offering's item family/subtype and tier.
- Fee remains 2 gold plus the affix count of both offerings.
- Original 35% / 50% / 15% branches remain unchanged, including caps and merged
  outcomes. The forecast uses the same rarity helpers and never consumes RNG.
- Equipped items, vault contents and saved-set storage are not offerings.

The workbench keeps object references rather than inventory indices. At final
confirmation it revalidates ownership, item fingerprints, tier, eligibility and
cost, then resolves fresh indices for the original transaction. Removal,
reordering, changed affixes, insufficient gold, double confirmation and failed
disk writes are covered by tests. Equal rolls are still distinct legal items.

Animation has no gameplay authority. One saved result starts a bounded,
client-local presentation, not the former multi-second Python reveal task with
per-line websocket refreshes. There is no ritual polling timer, particle loop,
full-screen flash or server-side animation sleep. Leaving, skipping, reduced
motion and losing focus cancel visual work without losing the item. The scene
also opts out of passive-regeneration-driven parent refreshes while editing.

The layout is a bounded desktop workspace. The page does not scroll. Long pack
lists and unusually long result affix lists use their own contained scroll areas;
the ritual and result actions remain reachable. Normal art/audio assets are
reused, with no new external requests or third-party assets.

## Verification

New unit tests cover explicit selection, identical items, all rarity combinations,
no preview RNG, fees, one legacy transaction, stale confirmations, reordered
inventory, disk rollback, and non-owning result records. Browser acceptance
exercises two real rituals, conservation of all other items, scroll/focus,
keyboard controls, retained results, reduced motion, and viewports from 800x500
to 2560x1080. The packaged executable is checked separately from source.

Release checks: 235 regression tests passed. Source and packaged acceptance each
completed two real rituals and 13 scene/viewport captures, without external
requests or browser JavaScript errors. Native WebView2 launch and post-crafting
package-integrity validation passed independently.

The prior 0.10.0 complete build remains under
`.build-backups/reimagined-0.10.0-fe2166f/PrismQuest`. Web/main and the preserved
original Steam editions are not modified. This redesign does not activate live
Steam services or alter the Concourse's release gates.
