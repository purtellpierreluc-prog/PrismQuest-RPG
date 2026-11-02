# PrismQuest Reimagined

This Windows RPG includes offline chronicles with hireable/permanent companions
and persistent town services for your current hero. It is not connected to your
web-game account, purchases, ladder, or characters.

## The Town and the Hearth

At the Inn, the resource cards show what one room will restore: 35% of health
and mana capacity, capped at full, with the original minimum recovery. Room
cost is based on your class. If you have a Monster Chain Combo, explicitly
confirm its reset. Resting keeps all items, experience and progression. A fully
recovered hero with no chain cannot accidentally pay for an empty rest.
The Vault retains its existing slot purchases, filters and free item movement.

The Town Crier now keeps recorded service spending with each chronicle across
restarts and climbs. Earlier spending that was never saved cannot be recovered.
The breakdown includes the Inn, Vault, Marketplace, Well, Crucible and charters.

**Bazaar**, **Guild Hall** and **Realm Ladder** are now direct Town and Chronicle
menu destinations. Concourse is no longer a game-mode detour or a second test
character. These are **local chronicle services**, not live Steam services.
Their scope is shown on every screen. Your old test-realm files are not deleted
or mixed into the main game.

In Bazaar, select a pack item, set a whole-number asking price, review the exact
item/price and confirm. It leaves the pack for saved local escrow; it is not
published to Steam players. Change Price saves an actual revised price. Return
to Pack retrieves that exact item for free. Ledger snapshots are records, not
additional owned items. Listings are same-mode only; SSF cannot trade. Empty
Browse shelves remain honest: no generated players, offers or buyers are added.
The NPC Marketplace remains separate and usable offline.

In Guild Hall, review a local charter before paying the original main-game
1,000g fee. Local invitation codes work among chronicles in this profile, not
Steam friends. Members can keep a persistent private board. A founder cannot
leave while other members remain; leaving as the only member dissolves the
charter without refunding its fee. Input fields have no polling refresh.

Realm Ladder shows actual local chronicle levels, wins and fastest recorded PQ
attempts. Filter by mode or explicitly compare all local chronicles; My Ascents
keeps the current chronicle's real PQ history. Beyond-60 levels are retained.
This screen never resets the ladder, replaces heroes or uploads editable saves.
Steam player trading, public guilds and global standings still require the App
ID, native authentication and an authoritative hosted backend. Upload alone
does not enable them, and local progression is not uploaded into that economy.

Save format 3 adds protected escrow ownership. Upgrading keeps a separate
`before-format-3-*` save in backups, outside the rotating ten-copy cleanup.
To revert to 0.14 or earlier, use the old executable and matching pre-upgrade
save. Older builds deliberately refuse format 3 rather than dropping listings.

## The Labyrinth Light Table

The Labyrinth now has actual passages and walls. Use arrows/WASD or the dock's
enabled direction buttons. Explore every room to wake the guardian; cleared
routes stay safe. Health/mana fonts, scouting mirrors and rare recovery
sanctuaries can appear once in new noncombat rooms. Journal records discoveries.
Scouting reveals information but does not count as exploration. Backtracking
does not repeat payouts or advance ability cooldowns.

Roster opens in the center, never above the party. Save companion names explicitly;
equipment and permanent companion rules are unchanged. Inventory does not abandon
the run. On small windows, long party/roster lists scroll inside their pane.

## Your Build and the Well

Hold **Ctrl** while hovering to inspect equipment, abilities and stat formulas.
Releasing Ctrl closes inspection. Ctrl plus keyboard focus also works.

Open Character & Stats from the Arena or Chronicle menu. Ctrl-hover or Ctrl-focus a core
stat to see its actual formula and the rounded changes from allocating one more
point. These previews spend nothing. Dexterity scales weapons and initiative,
not attack speed: Arena and Well initiative decides the first actor, while
Labyrinth uses party order. Hover the derived totals for their rules too.

Proficiency trains the family actually used on a successful hit. Each family
level adds 1% of raw item damage, additive with the item's Enhanced Effect
contribution, not 1% of final damage. It does not improve affixes or reduce mana
costs. Existing proficiency power and leveling thresholds are unchanged.

At the Well of Evil, select a Common item from your pack, review the named item
and 10-gold fee, then Cast Offering. No item is selected automatically. Victory
has a 50% chance to return an item of the offering's type and tier; rarity uses
normal Magic Find and affixes use the Well's favorable roll. A stronger item is
not guaranteed. Defeat or withdrawal consumes the offering and fee without loot.

The last answer is a read-only record. Returned gear is saved into your pack
before the reveal, with no claim button. Reveal now or Escape skips presentation;
reduced motion/item-animation preferences bypass it. A temporarily interrupted
encounter can continue in the same open game without a second payment. A failed
outcome save offers Retry Saving Outcome, retaining that exact rolled answer.
These recovery stages are in memory, not new cross-process checkpoints: retry
before closing the game. The original Hardcore death rules still apply.

## The Crucible

From Town, open **Transmutation**. Pick a **Form** from your pack, then a different
Fine-or-better **Sacrifice** of the same tier. The form's item type/tier survive;
the rarity and affixes are newly rolled. Check the real probabilities and gold
fee, choose **Review Transmutation**, then confirm. Both offerings are consumed.

Your result is saved into the pack before the reveal. Skip with Escape or the
on-screen button; reduced-motion/item-animation settings bypass it. **Inspect
in Inventory** opens the real item. **Use as Next Form** starts another deliberate
pair. **Last Result** is only a record, not an extra item to claim.

The fee is still 2 gold plus one gold per affix across both offerings. There is
no promise that the result will be stronger. Equipped, saved and vaulted items
are not consumed by the workbench.

## The Exchange and Prismatic Quest

Marketplace presents three curiosities. Click one to inspect full stats and
compare against your current equipment. Review Purchase, then confirm its price.
Purchased gear goes to the pack, not directly onto your hero. Stock changes at
the existing level milestones, never simply because you reopened the shop.

At level 60, approach Prismatic Quest to review its entry fee, blind matching
odds and carryover rules before paying. Colors do not reveal correct pairings.
Choose a light, then a vessel, or drag a light to aim the pairing. Neither action
commits it. Review the named pair and press **Commit Offering** when ready; one
wrong offering ends the rite. The prism listens, then a correct binding lights up
and joins your binding history. The last seal opens before the climb's aftermath.
**Quick Reveal**, or Escape while waiting, shortens the presentation without
changing its result. Bound choices stay in place. You can step away between offerings after confirming
that the entry fee will not be refunded.

If a reveal is interrupted while the game process remains open, **Continue
Offering** resumes its committed pair. It does not spend another fee or roll a
new pairing. A failed save offers **Retry Saving Outcome**. Unfinished rites are
not new cross-process save checkpoints, so do not quit the game to reroll them.

If a screen update fails, **Retry View** redraws the current state without
resetting your run. Render errors are recorded in the local desktop log.

The aftermath records the outcome before asking you to continue. Normal success
and failure end this hero's climb, preserving the existing gear/gold/proficiency
carryover. Successful completion of the final class preserves your current hero
and opens the way back to Town or the Labyrinth. The chapter's quiet score uses
your existing audio settings; reduced motion removes decorative effects.

## Install and Launch

Keep the complete PrismQuest folder together, including `_internal`.
Run PrismQuest.exe. Python does not need to be installed.
The Microsoft Edge WebView2 Evergreen Runtime is required. If missing, the game
shows installation instructions; it does not silently download an installer.

## Progression

Each Core, SSF, and Hardcore chronicle is independent. Prestige unlocks the next
class in its local path and preserves the existing carryover rules. Hardcore
death still applies the existing equipped-gear loss rules.
Completing the final class path records the victory but does not automatically
erase any local chronicle. Keep that hero and continue into the Labyrinth.
There are no server-driven/calendar resets in this offline alpha.
The local NPC Marketplace remains available. Bazaar, Guild Hall and Realm Ladder
are now direct town destinations for the current chronicle, with explicitly
local records. The former Concourse preview is no longer part of normal play.
Live Steam trading, public guilds/rankings and shared online Labyrinth still
require the separately configured authoritative network service.

## Controls and Display

F11 toggles fullscreen. Arrow keys/WASD move through the Labyrinth when your party
is exploring. Keyboard shortcuts can be configured in Settings > Hotkeys.
Long inventories and references scroll inside their panels, not the main window.
Settings > Desktop remembers window size/fullscreen and offers reduced decorative
motion without slowing combat. System reduced-motion preference is respected.
Mouse and keyboard are the supported inputs; controller/Deck support is not claimed.

## Audio

Settings > Audio has separate effects/music volume sliders, master mute and
switches for music, combat textures, reward chimes and background muting.
The quiet defaults are 35% effects and 18% music; Restore Quiet Defaults restores
only these audio settings, not your character or combat preferences.
Test Level-up, Test Rare Find and Test Combat let you hear the balance immediately.
Audio starts after your first click or keypress. It fades out while the window is
unfocused by default, without a backlog of sounds when you return. Common item
drops have no chime. Audio is entirely local and needs no internet connection.
Your choices are saved in `audio.json` alongside, but separately from, your saves.

## Saves and Recovery

This experience fork saves to `%LOCALAPPDATA%\PrismQuest\SteamEditionReimagined`,
outside the installation. Both earlier editions' save profiles are left untouched.
The two editions do not share automatic progress. To return to the preserved
version, launch PrismQuest.exe from SteamEditionVisual (Nocturne) or SteamEdition.

## Decide, Fight, Improve

Town recommends a next step based on your health, unspent points and progression.
The other roads remain your choice. In the Arena, Target controls difficulty;
Call Challenger starts automatic rounds. Victory shows earned XP progress and
the actual new item, if one dropped. Inspect This Find opens that exact owned
item in the workbench. It does not grant a second item or auto-equip it.

Click a pack entry to lock the selection. Hovering other entries does not replace
your comparison. The green/red changes show actual character stat deltas from
equipping the selection, including proficiency; weapon/spell figures are averages
before target defenses, not guaranteed damage. Rarity alone is not an upgrade.

The Arena's Last Drop control beside the chain counter remains available during
the next fight. Hover or focus it to inspect the full latest-drop record, even
if you already moved or sold that item. It is read-only and resets for a new run;
it is not a second inventory item. A newer drop replaces the record.
Quick arrival/result effects do not delay combat and respect reduced motion.
Colored species edges and atmospheric signatures are flavor; the separately
labeled blue/silver portrait halo still identifies actual defensive strength.

Character & Stats moves allocation and proficiency away from the combat stage.
The Chronicle menu holds settings, records, class management and optional scene
help. First-fight, first-death and level-5 community prompts remain; optional
service tutorials no longer interrupt every first visit.

Saved Sets is a separate archive for later runs, grouped by item type and tier.
Expand/collapse a family to see its marks. Empty marks help plan a future climb;
"Filtered item" means gear is stored there but does not match your current filters.
Hover a saved piece for full stats, click to select, then Equip Saved or Restore
Saved to move it back to your pack. Saving into an occupied type/tier returns the
previous saved piece to your inventory. Protected gear persists through Prismatic
Quest into the next run; it is not a duplicate inventory copy.

Item borders identify type; background shading identifies rarity. The small visual
key explains the colors. Names/icons/text repeat the same information. In Arena,
silver monster auras indicate high armor and blue high magic resistance for that
level; labels and exact stats remain visible, and both cues can appear together.
Settings > Desktop can create a manual backup and open the save folder.
Do not delete this profile when replacing or uninstalling an alpha build.
Local save format 2 reads earlier format 1 saves without discarding fields; the
next successful save keeps the original in rotating backups. Older executables
will refuse format 2, so keep the old save backup when rolling back builds.

If a save fails, stop making progress until storage space/permissions are fixed.
Item actions roll back their staged changes if they cannot commit to disk.
If another program replaces the save, close and reopen PrismQuest instead of
overwriting the changed file. Do not run two copies against the same profile.
Unreadable saves are not treated as empty new characters. A valid rotating backup
can be recovered, with a warning; existing damaged files are preserved.

## Support Data

Settings > Desktop > Export Local Diagnostics creates a JSON report in the local
logs folder. It contains system/runtime versions, save health, and aggregate save
costs, not character names, equipment, account IDs, save contents, or log contents.
Nothing is uploaded automatically. Review any files before sharing them.

Command-line support options: `--version`, `--diagnostics`, and `--verify-package`.
Browser/port/profile arguments are developer diagnostics, not multiplayer hosting.
Package verification checks installed file hashes; it is not code signing.
