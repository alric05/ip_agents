"""Diagnostic: check whether C19904 GT publications exist in Derwent.

Runs one direct PN= lookup per GT publication and prints what Derwent
returns. Used to decide whether the agent's failure to surface these refs
is a ranking problem (Derwent has them, just buried) or an indexing gap
(Derwent doesn't have them at all).

Usage:
    .venv/bin/python scripts/diagnose_gt_retrievability.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.clients.derwent import _derwent_fld_search

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

GT_PUBS = [
    ("IL279932B",       "Floating solar panel array installation and mooring and method of assembly"),
    ("US11319035B2",    "Floating type solar power generation equipment stage device"),
    ("US20210214056A1", "Floatable Array Ready Solar Module Mounting Device, System and Method Of Solar Energy Collection"),
    ("US9729101B1",     "(title not recorded in GT file)"),
]

print()
print(f"{'Pub':<20} {'Derwent hit?':<15} {'Returned title (first 80 chars)':<85}")
print("-" * 120)

for pub, gt_title in GT_PUBS:
    query = f"PN=({pub});"
    result = _derwent_fld_search(query, size=5)

    if isinstance(result, str):
        print(f"{pub:<20} {'ERROR':<15} {result[:80]}")
        continue

    if not result:
        print(f"{pub:<20} {'NO HIT':<15} (Derwent returned zero rows — pub not indexed)")
        continue

    first = result[0]
    ret_pub = first.get("publication_number", "")
    ret_title = first.get("title", "") or first.get("dwpi_title", "")
    print(f"{pub:<20} {f'YES ({len(result)} rows)':<15} {ret_title[:80]}")
    if ret_pub and ret_pub != pub:
        print(f"{'':<20} {'(normalized)':<15} returned pub_number = {ret_pub}")
    print(f"{'':<20} {'GT title was:':<15} {gt_title[:80]}")

print()
print("Interpretation:")
print("  - All YES → Derwent has them; ranking problem. Investigate cite-chasing / vocabulary.")
print("  - Mix     → Partial gap. Apply ranking fix to hit subset; accept miss subset.")
print("  - All NO  → Derwent doesn't index these. Need a second source (Google Patents, Lens, USPTO).")
