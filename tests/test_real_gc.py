"""Regression test against the real collector, not a mocked gc module.

Runs in a subprocess so freezing a heap never touches pytest's own.
"""

import json
import subprocess
import sys
from pathlib import Path

from custom_components.gc_manager.const import FROZEN_GEN2_THRESHOLD

_PROBE = """
import gc, json, logging, sys
from custom_components.gc_manager.gc_controller import GcController

gen2 = 0
def cb(phase, info):
    global gen2
    if phase == "stop" and info["generation"] == 2:
        gen2 += 1
gc.callbacks.append(cb)

def churn():
    # Mostly cyclic garbage plus a trickle of survivors, like a busy event loop.
    keep = []
    for i in range(1_000_000):
        a = []
        a.append(a)
        if i % 50 == 0:
            keep.append([None] * 3)
    return keep

def run():
    global gen2
    gc.collect()
    gen2 = 0
    survivors = churn()
    return gen2

heap = [[i, [i]] for i in range(1_000_000)]  # the long-lived HA object graph
out = {"unfrozen": run()}
gc.freeze()
out["frozen_default"] = run()
controller = GcController(None, logging.getLogger("probe"))
if sys.argv[1] == "raise":
    controller._raise_gen2_threshold()
out["frozen_raised"] = run()
out["threshold2"] = gc.get_threshold()[2]
print(json.dumps(out))
"""


def _probe(*, raise_threshold=True):
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, "raise" if raise_threshold else "skip"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_frozen_heap_makes_gen2_frequent_and_the_raise_makes_it_rare_again():
    out = _probe()
    # The 25% guard keeps gen-2 away while the heap is unfrozen...
    assert out["unfrozen"] == 0
    # ...but a frozen heap drops out of the guard's total: the bug.
    assert out["frozen_default"] >= 1
    # The controller's raise puts gen-2 back to rare.
    assert out["threshold2"] == FROZEN_GEN2_THRESHOLD
    assert out["frozen_raised"] == 0


def test_probe_detects_a_missing_raise():
    """Guard the test itself: without the raise the churn must still show gen-2."""
    out = _probe(raise_threshold=False)
    assert out["frozen_raised"] >= 1
