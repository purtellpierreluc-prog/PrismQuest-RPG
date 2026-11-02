# Labyrinth of Light / The Light Table / 0.16.0

## Presentation

The party, play stage and expedition dock occupy three separate bounded columns.
No movement/companion expansion is positioned over the party. Roster management
replaces the central workspace and leaves the party visible. Name drafts do not
submit or refresh while typing; Save Name is explicit. Equipment uses the existing
exact-transfer operations. Gold costs, permanent ownership, proficiency and the
five-member limit are unchanged. Inventory remains accessible without leaving.
Companion-issued starter gear stays bound and is retired when replaced, as before;
actual player items return to the pack when replaced/cleared. Conservation checks
distinguish these deliberately different rules rather than duplicating issued gear.

Five members fit without party scrolling at 1280x720 and above. Small windows use
internal scrolling rather than cropping content or scrolling the whole page.
The map and combat occupy the same bounded stage, including one-boss encounters.
The boss has contained artwork, a full HP bar and basic stats. Three normal
monsters remain side-by-side. Prism choices keep the existing vote deadline and
display it; boon and burden have separate readable colors. Keyboard movement is
disabled in management/journal screens, inputs and combat.

Existing Ctrl-hover inspection, ready abilities, Warlock healing mode, tank
ownership and red/green pressed states remain. Compact party health/mana bars
retain their stable real-engine patch IDs; this is not a new combat loop.

The requested Arena, Character/Stats and Town explanatory lines are removed.
Monster species/defense captions are removed from Arena while their subtle visual
color cues and actual stats remain. Stat formula inspections are still accurate;
removing presentation copy does not change STR/DEX or initiative mechanics.

## Maze Rules

- A 7x7 connected maze has real walls, branching paths, dead ends and up to four extra
  passage connections for loops. Every room is reachable. Blocking a direction
  does not move the party or advance exploration/ability recovery.
- Layout and room outcomes use stable session/floor seeds, not deployment times,
  global random state or repeated random checks on movement. Generated topology
  is cached, capped at 128 floors. Restarting does not reroll it.
- Existing visited/resolved rooms and combat checkpoints remain intact on load.
  A previous open-grid run gains a connected maze without resetting its progress.
- Each new room keeps the original 50% combat / 50% noncombat split. Cleared
  paths stay safe. Backtracking is necessary, but does not repeat encounters,
  discoveries or cooldown progress.
- Explore/resolve all 49 rooms to trigger the original guardian automatically.
  Its gold, item and exactly-one-level reward rules are unchanged. Subsequent
  floor monster levels and prism modifiers remain controlled by the old engine.

## Added Discovery Log

These odds apply **within the noncombat half** of first-visit rooms. Start/gate
rooms do not grant discoveries. A deterministic independent roll chooses:

| Room | Chance | Effect |
| --- | --- | --- |
| Still Light | 60% | Quiet passage, no payout. |
| The Living Font | 14% | Restore 12% max health to each standing ally. |
| Aether Well | 14% | Restore 18% max mana to each standing ally. |
| The Cartographer's Mirror | 8% | Scout up to three nearby unvisited/unscouted rooms. Reveal their information without entering, resolving, granting rewards or advancing ability cooldowns. |
| Sanctuary of Echoes | 4% | Revive one fallen ally at 15% max health. If nobody is fallen, restore 6% max health to standing allies instead. |

Health effects respect existing Labyrinth healing modifiers and resource caps.
Mana does not exceed capacity. Fonts do not resurrect fallen allies; only the
rare sanctuary does. The screen reports actual gains, including no gain if full.
Discoveries resolve immediately, so there is no blocking chest/choice state that
can strand movement. No extra gold, items or XP are created by discoveries.

First-visit position, consumed room and resource effects commit in one checkpoint.
Failed writes restore them together. Revisits, reloads and UI refreshes do not
reclaim an effect. Journal keeps the last 60 actual discoveries for the current
run, including floor and room. A finite local receipt reveal respects reduced
motion and Lab low-load settings; it does not add a combat delay or polling loop.

## Verification and Scope

Following the project's ECC red-first workflow, tests cover 40 deterministic
connected layouts, reciprocal/bounded passages, real wall rejection, first-visit
effects, resource caps/reload, sanctuary revival, scout-only cooldown behavior,
save failure rollback, old checkpoint continuation and complete floor/boss/prism
progression. UI acceptance checks use only disposable profiles and local requests.
No normal player saves or hosted-main deployment are used for QA.

Final verification: 417 tests and lint passed. Source browser acceptance passed
29 layout/interaction checks at 800x500, 960x600, 1280x720 and 1920x1080; separate
boss and prism-choice fixtures passed all four sizes too. The packaged playthrough
passed cleaned scenes, five-member layout, tank state, Ctrl inspection, stable
name entry, exact player-item equip/return conservation, inventory return and
legal maze movement. Real three-monster combat was also exercised separately.
A cold packaged restart retained position, maze, roster name and item counts.
Native WebView2 startup fit 1084x681 content into its 681px client height.

The 15-second packaged title-idle sample received no server WebSocket frames.
The five-member combat sample received 9 frames / 61,092 local payload bytes,
with 0.744s renderer task time and 0.093s layout time. No page errors or external
requests occurred. These are short headless-Chrome samples, not a speedup claim,
whole-process CPU measurement, network framing total or long-session soak test;
combat may finish during a sample. No new polling or combat cadence was added.

Package integrity passed for 1,007 files and the preserved 0.15 build for 1,006.
All 154 original art files match the previous build. Existing Steam release and
license-audit gates still apply; this is not a certified Steam release.

This remains the isolated Windows Steam conversion, not a claim of enabled
Steam networking. No SQL change or new Steam identifiers are needed here.

## Rollback

Previous source: `89890dc`, bookmark `steam-reimagined-v0.15.0`.
Complete verified previous executable:
`.build-backups/reimagined-0.15.0-89890dc/PrismQuest`.
Normal rotating save backups remain enabled. This release retains format 3;
there is no item-ownership migration or production save overwrite. Keep an
appropriate save backup when reverting editions, especially an in-progress run.
