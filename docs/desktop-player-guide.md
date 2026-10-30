# PrismQuest Reimagined

This build is an offline Windows solo RPG with hireable and permanent companions.
It is not connected to your web-game account, purchases, ladder, or characters.

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
The local NPC Marketplace remains available; online Bazaar, courier, guilds,
shared ladder, and multiplayer are not included.

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
