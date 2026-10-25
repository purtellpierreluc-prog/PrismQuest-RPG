# Performance and Layout Audit, October 25, 2026

Baseline: `85212d5c13a66239fa7ab626c360e42bc7f98178`.
Rollback tag: `backup/live-2026-10-25-before-performance`.

## Changes

- Serialize each inventory/equipment item once per character save. Loaded items own their stat dictionaries, so combat and save snapshots cannot mutate each other's affixes.
- Skip character reconstruction and saves when a Lab snapshot has not changed. Apply solo updates once before persisting them, including companion progress.
- Read shared Lab snapshots off the asyncio event loop. Discard reads if the character, expedition, or local snapshot changed while the request was outstanding.
- Patch Lab health/mana meters, damage effects, monster headings, and round text in place during combat. Rebuild the scene when the encounter, party structure, tank role, or scene changes.
- Respect server combat deadlines and reject callbacks for an outdated encounter step. Preserve fractional seconds in round deadlines.
- Coalesce redundant pending render requests and skip unnecessary button restyling.
- Preserve zero-valued selections for prism voting, marketplace hovering, roster equipment, and vault confirmations. Preserve zero HP and mana when restoring combatants.
- Resolve victories from reflected damage immediately.
- Keep map and encounter dimensions stable, fit the maze to its container, retain three monster columns, and scale portrait/image layout on phones.
- Replace the vault's fixed minimum-width columns with a responsive grid and independently scrollable item lists.
- Make tank button state colors override the general button theme.

## Verification

Run offline regression tests with `python -m pytest tests/test_runtime_regressions.py -q`.
The suite uses temporary storage, disabled cloud credentials, and mocked persistence.

31 tests passed, covering serialization compatibility and snapshot independence, saved sets, vault deposit/withdrawal, sales, companion equipment, zero-health characters, first reward voting, stale callbacks, asynchronous polling, arena combat, five-member/three-monster round order, and boss rewards awarded once.

Targeted Ruff checks passed: `F821,F823,F811,B006,B023,ASYNC`. Python compilation passed.

Headless Chrome checks passed at 1440, 1024, 768, and 390 pixel widths. Tested maze bounds, single-boss and three-monster HP bar bounds, portrait identity across multiple rounds, tank colors, vault bounds, and first-item deposit/withdrawal. No JavaScript page errors were observed.

## Local Measurements

These are controlled local comparisons, not production-wide savings guarantees.

| Operation | Before | After |
| --- | ---: | ---: |
| Serialize a 200-item character | 1.50 ms | 0.080 ms |
| Validate a Lab snapshot | 6.50 ms | 2.22 ms |
| Apply an unchanged character snapshot | 36.34 ms | 0.336 ms |
| Websocket payload for three Lab combat rounds | 168,293 bytes | 2,383 bytes |

The websocket comparison excludes the initial page load. The combat test used the same local setup with five party members. Actual results depend on items, browser, latency, and player activity.

No database migration, ladder reset, inventory migration, dependency upgrade, or production-account operation is part of this release. Multiplayer network failures were exercised offline; production party play still warrants observation after release.

## Review Guidance

Consulted the everything-claude-code repository's [Python patterns](https://github.com/affaan-m/everything-claude-code/blob/main/skills/python-patterns/SKILL.md) and [performance guidance](https://github.com/affaan-m/everything-claude-code/blob/main/rules/common/performance.md), especially explicit state changes, avoiding repeated work, I/O concurrency, and incremental verification. No repository hooks or agent scripts were installed.
