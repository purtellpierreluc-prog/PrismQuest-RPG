# PrismQuest Nocturne Visual Edition

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

## Saves and Recovery

This visual fork saves to `%LOCALAPPDATA%\PrismQuest\SteamEditionVisual`, outside
the installation. The earlier edition's `SteamEdition` profile is left untouched.
The two editions do not share automatic progress. To return to the preserved
version, launch PrismQuest.exe from the original SteamEdition folder.
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
