# GC Manager

A Home Assistant integration that manages Python's garbage collector to keep
event-loop pauses small on large instances.

## Why

On a large Home Assistant instance the Python heap can hold millions of
long-lived objects (entities, integration state, caches). CPython's periodic
**gen-2** garbage collection walks that whole set, and because it holds the GIL
while it runs, the event loop freezes for its duration — often hundreds of
milliseconds to well over a second, recurring every few minutes. That surfaces
as laggy automations and stalled updates.

`gc.freeze()` moves the current long-lived objects into a permanent set the
collector skips, so subsequent gen-2 sweeps only scan what has been allocated
since — dramatically shrinking the pause. This integration schedules that, and
keeps it effective over time.

## What it does

- **Freeze on startup** — after Home Assistant finishes starting (plus a short,
  configurable settle delay, so startup-transient objects aren't frozen), run
  `gc.collect()` then `gc.freeze()` once, exempting the startup object graph
  from future collections. This is the core fix.
- **Periodic re-freeze** (optional) — new long-lived objects accumulate after
  the startup freeze and the pause slowly creeps back up. A periodic
  `collect()` + `freeze()` re-absorbs them, holding the pause near its floor.
  Cheap, but frozen-then-dead objects are not reclaimed until maintenance.
- **Daily maintenance** (optional) — once a day, `unfreeze()` + `collect()` +
  `freeze()`: a full reset that reclaims anything frozen earlier that has since
  become garbage (the small leak the cheap re-freeze leaves), then re-freezes
  the current live set. (When daily maintenance is off, the periodic pass does
  this full reset instead, so that leak can't accumulate.)
- **Gen-2 threshold raised while frozen** (automatic) — CPython only runs a
  full collection when the objects pending promotion exceed 25% of the
  long-lived total, and a frozen heap drops out of that total, so once frozen
  the guard passes on nearly every gen-1 pass (a full collection every ~85 s
  on a 13k-entity instance). After each freeze the gen-2 threshold is raised
  to 1000 and put back on unfreeze or unload.
- **GC threshold override** (optional) — raise CPython's `gc.set_threshold()`
  values so collections run less often; off by default, restored on unload.

All of the above are configurable in the options flow; a freeze with neither
reset schedule is rejected there. Reloading keeps the heap frozen; disabling or
removing the integration unfreezes it. Services
`gc_manager.freeze`, `gc_manager.unfreeze`, and `gc_manager.maintain` expose the
operations manually.

Diagnostic sensors, all under one **GC Manager** device, report the frozen
object count (and, opt-in, the tracked count, whose sample walks the unfrozen
heap), the gen-2 pause (last and peak since the last freeze),
the last operation and how much it reclaimed, and per-generation gc
counts/thresholds/stats; a binary sensor reports whether automatic gc is on.

## Caveats

- Each operation holds the GIL while the collection runs, so it briefly pauses
  the loop itself — schedule the heavier daily maintenance for a quiet hour.
- Freezing exempts objects from collection permanently; the periodic re-freeze
  can slowly retain objects that later die, which the daily maintenance clears.
- This does not reduce the rate of object churn — it reduces how much the
  collector must scan. If a single integration is allocating heavily, address
  that too.

## Installation

Install via HACS as a custom repository, or copy `custom_components/gc_manager`
into your `config/custom_components`, then add **GC Manager** from Settings →
Devices & Services.
