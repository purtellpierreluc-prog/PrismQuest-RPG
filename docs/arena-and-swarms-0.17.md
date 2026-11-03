# Quiet Indicators / Swarming Light / 0.17.0

## Arena and Ladder

The requested BUILD DECISION / Turn experience into power copy no longer appears
in the compact Arena journey. Town's existing build guidance is not removed.
The six always-visible hero combat numbers are replaced by a 25px line-chart
icon; a matching book icon shows all six proficiency families, current level,
progress/threshold and a compact progress line. Active families are accented.
The build screen no longer repeats the proficiency table. Neither icon requires
a server request to inspect. Both use the existing stable Ctrl-hover/Ctrl-focus
portal, including during combat refreshes; key release and blur still close it.

The Realm Ladder's Class filter defaults to All classes. Selecting a specific
class switches sorting to Fastest Ascent, using successful matching-class PQ
entries and genuine recorded `fastest_masterquest_seconds` class bests from older
builds. Failed, zero and nonfinite times cannot become records. Missing historical
attempts are not fabricated. The level/victory columns remain current chronicle
stats; a different recorded PQ character name is identified. My Ascents obeys the
same class selection. These are still local chronicle records, not Steam/global
rankings, and there is no SQL migration or public leaderboard reset.

## Lab Swarm Rules

The existing engine already resolved a complete party/monster round in one
guarded state update. This remains a single batch, not new threads, concurrent
save writers or per-character timers. Every standing party member acts in stable
party order within the batch, followed by each surviving monster. All updated
health bars are published together. Multiple hits on one target now produce one
summed pop-up, instead of overwriting earlier hits with only the last hit.

Default round pacing is 1.0s at the standard 1,000ms combat-delay setting, down
from 1.5s, with a 0.9s minimum. The separate slow-cadence option retains a minimum
2.25s delay, and low-load mode continues to disable damage pop-ups and bar motion.
There is no new polling or one-socket-message-per-actor behavior.

New normal packs:

| Party Size | Normal Pack |
| --- | --- |
| 1 | 2 monsters |
| 2 | 50% chance of 2 or 4 |
| 3 | 4 monsters |
| 4 | 50% chance of 4 or 6 |
| 5 | 6 monsters |

Normal Lab monster HP, damage endpoints, physical armor, magic resistance,
armor penetration and initiative are halved, with safe integer rounding/minima.
Accuracy, critical probabilities/multipliers and evasion are intentionally retained
to avoid turning faster combat into missed-attack waiting. Bosses remain one
full-strength guardian. Arena/Well monsters are unchanged. The normal pack's
existing reward budget remains per fight, not per monster: no extra gold/XP
or multiplied item payouts were introduced. Packs fit one or two bounded rows.

The new-room encounter threshold is 40%, a 20% relative reduction from 50%, not
a 20-percentage-point reduction. Already-generated tile kinds, active enemies,
room discoveries, maze geometry and checkpoints are retained without rerolling
or repeated stat reductions. New spawns/new floors use the new tuning.

## Town Artwork

Final asset: `Assets/TownScene/Town_Reimagined.webp` (1536x1024, genuine alpha,
572,138 bytes). Runtime prefers this image only in the desktop edition. Original
`Town.png` and `Town.webp` remain untouched and available as fallback/reference.
Existing content-versioned asset URLs/caching are unchanged. No in-image text or
UI overlays are baked into the new art.

Created with the built-in image generation tool, using the previous town image
as the reference/edit target. Only WebP encoding was performed afterward; no
Python background removal, recoloring or compositing was used. Generated source:
`C:/Users/Pierre-Luc Purtell/.codex/generated_images/019db235-bb4e-7921-98a2-7db4add01ba1/exec-29b96ca4-0af0-4d5a-819b-2346d0add19b.png`.

### Final Prompt

Use case: style-transfer / stylized-concept. Asset type: production town-square
game illustration for PrismQuest, a restrained dark fantasy RPG. Input image is
the existing town asset to redesign, not a UI screenshot. Reimagine it at a much
higher professional art direction and craftsmanship level while preserving its
recognizable landmarks and loose isometric layout: the timber-framed inn on the
upper left, the old stone well and bare tree near the upper center, market stalls
in the lower center/right, the circular arena on the lower right and the alchemical
transmutation circle on the lower left, connected by a few cobbled paths. The goal
is a beautiful sanctuary crossroads between adventures. Match the game's elegant
black-and-white silhouette vocabulary: deep charcoal/black cut-paper silhouettes,
precise ivory/silver etched edge lighting, tiny warm bone-white window accents,
coherent perspective and believable architecture. More refined, cohesive, richly
designed shapes than the reference, but readable at small in-game scale; no muddy
high-frequency clutter. Strong visual hierarchy, evocative calm atmosphere,
generous breathing room between landmark clusters. Wide 3:2 composition with all
buildings, arena, circle, branches and paths fully inside the frame, clean margins.
Genuine transparent alpha background so the composition floats cleanly on the
existing deep teal-black UI; no opaque rectangular backdrop, checkerboard pattern,
grey matte or surrounding landscape slab. No labels, no signs with lettering, no
words, no UI, no logos, no watermark. Premium polished hand-inked game environment
illustration, not photorealism, not a colorful cartoon. Preserve transparency and
do not clip edges.

## Verification

- All 432 automated tests and lint checks passed. New regressions cover normal
  pack size, exact power scaling, unchanged bosses/hit consistency, 40% threshold,
  preserved generated rooms, all 11 actors in one guarded update, duplicate-step
  rejection, summed damage feedback, read-only hover values, successful class-only
  records and legacy class bests without invented attempts.
- Source and packaged browser checks passed at 800x500, 960x600, 1280x720 and
  1920x1080. Both indicators remain 25px, require Ctrl, and proficiency inspection
  stays visible on the same portal node through real Arena combat refreshes.
  Class fixtures return the correct 90s/30s records; My Ascents obeys the filter.
  New town art loads under its content-versioned WebP URL. Six monster HP bars
  fit within the bounded play stage at every size.
- A real packaged five-member/six-monster fight completed to exploration and
  persisted its result with no server/page errors. Its 15s rendering sample
  received 11 local WebSocket frames / 64,005 payload bytes, used 1.291s renderer
  task time and 0.152s layout time. Title idle received no server frames in its
  15s sample. These are short headless-Chrome observations, not a controlled
  speedup comparison, native/whole-process CPU benchmark or long-session soak.
  The final minor swarm styling also omits redundant per-sprite blur shadows.
- Native WebView2 startup passed at a 1084x681 client size with 681px document
  height. Package integrity passed for 1,008 files; the 0.16 backup passed for
  1,007. All 154 previous art files remain byte-identical; one new WebP is added.

## Safety and Rollback

Prior source: `dda0b23`, tag `steam-reimagined-v0.16.0`. The verified complete
previous executable is preserved in
`.build-backups/reimagined-0.16.0-dda0b23/PrismQuest`. Save format remains 3.
No normal AppData profile, external account or hosted-main deployment is used
for testing. Existing Steam-release/license gates still apply.
