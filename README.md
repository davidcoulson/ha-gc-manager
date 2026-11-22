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
  Cheap, but frozen-then-dead objects are not reclaimed until maintenance. The
  forced `collect()` holds the GIL, so with a _re-freeze pause target_ set (ms)
  each slot re-freezes only once an automatic gen-2 pause since the last freeze
  has reached that target — the cost is paid when the unfrozen heap has actually
  grown enough to hurt, not on a clock. 0 (default) re-freezes on every slot;
  the target is ignored when daily maintenance is off, because the periodic pass
  is then the full reset that bounds memory.
- **Daily maintenance** (optional) — once a day, `unfreeze()` + `collect()` +
  `freeze()`: a full reset that reclaims anything frozen earlier that has since
  become garbage (the small leak the cheap re-freeze leaves), then re-freezes
  the current live set. (When daily maintenance is off, the periodic pass does
  this full reset instead, so that leak can't accumulate.)
- **GC threshold override** (optional) — raise CPython's `gc.set_threshold()`
  values so collections run less often; off by default, restored on unload.

All of the above are configurable in the options flow. Services
`gc_manager.freeze`, `gc_manager.unfreeze`, and `gc_manager.maintain` expose the
operations manually.

Diagnostic sensors, all under one **GC Manager** device, report the frozen and
tracked object counts, the gen-2 pause (last and peak since the last freeze),
the last operation and how much it reclaimed, and per-generation gc
counts/thresholds/stats; a binary sensor reports whether automatic gc is on.

Every operation also fires a `gc_manager_operation` event on the bus, after the
sensors have updated, so an automation can react to a slow freeze without
polling. Its data is `action`, `collected`, `frozen_before`, `frozen_after`,
`duration_ms` and `at` (ISO 8601). `action` is one of `startup freeze`,
`periodic re-freeze`, `manual freeze (service)`, `unfreeze`,
`daily maintenance (unfreeze+collect+freeze)`,
`periodic maintenance (unfreeze+collect+freeze)` or
`manual maintenance (service)`.

The integration's **Download diagnostics** includes the options as stored
(before any rounding or defaults), the interpreter's gc thresholds and stats,
and the controller's cached telemetry, which is empty if the integration isn't
loaded.

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
