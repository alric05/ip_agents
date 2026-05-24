"""Vocabulary variant test: which landscape-query shape surfaces the GT refs?

We now know (from diagnose_gt_retrievability.py) that all four C19904 GT
refs are retrievable by direct PN= lookup. They just aren't ranking high
on the broad landscape query. This script tests a handful of vocabulary
variants at max_results=50 and reports how many GT refs each variant
surfaces.

Usage:
    .venv/bin/python scripts/diagnose_vocab_variants.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.clients.derwent import _derwent_fld_search

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

GT_PUBS = {"IL279932B", "US11319035B2", "US20210214056A1", "US9729101B1"}

VARIANTS = [
    (
        "V0 current baseline",
        "CTB=((floating OR float* OR pontoon* OR buoyan*) AND (solar OR photovoltaic OR PV));",
    ),
    (
        "V1 + mounting/installation/deployment",
        "CTB=((floating OR float* OR pontoon* OR buoyan*) AND (solar OR photovoltaic OR PV) "
        "AND (mounting OR installation OR deployment OR array OR assembly));",
    ),
    (
        "V2 + mooring/anchor",
        "CTB=((floating OR float*) AND (solar OR photovoltaic OR PV) "
        "AND (mooring OR anchor* OR tethering));",
    ),
    (
        "V3 + equipment/device/apparatus",
        "CTB=((floating OR float*) AND (solar OR photovoltaic OR PV) "
        "AND (equipment OR device OR apparatus OR module OR stage));",
    ),
    (
        "V4 GT-vocab blend (installation+mooring+device+array)",
        "CTB=((floating OR float*) AND (solar OR photovoltaic OR PV) "
        "AND (installation OR mooring OR mounting OR device OR array OR deployment));",
    ),
    (
        "V5 narrow older-art cutoff (PY<=2022) + V4 vocab",
        "CTB=((floating OR float*) AND (solar OR photovoltaic OR PV) "
        "AND (installation OR mooring OR mounting OR device OR array OR deployment)) "
        "AND PY<=2022;",
    ),
    (
        "V6 PY window 2016..2022 + V4 vocab",
        "CTB=((floating OR float*) AND (solar OR photovoltaic OR PV) "
        "AND (installation OR mooring OR mounting OR device OR array OR deployment)) "
        "AND PY=(2016-2022);",
    ),
]


def _pubs_in(result) -> set[str]:
    if isinstance(result, str) or not result:
        return set()
    pubs: set[str] = set()
    for p in result:
        pn = (p.get("publication_number") or "").strip("_")  # strip trailing _
        if pn:
            pubs.add(pn)
    return pubs


print()
print(f"{'Variant':<50} {'Total':<8} {'GT hits':<10} {'Which GT refs surfaced'}")
print("-" * 130)

for name, query in VARIANTS:
    result = _derwent_fld_search(query, size=50)
    if isinstance(result, str):
        print(f"{name:<50} ERROR    -          {result[:60]}")
        continue
    pubs = _pubs_in(result)
    gt_hits = pubs & GT_PUBS
    print(f"{name:<50} {len(pubs):<8} {len(gt_hits)}/4        {sorted(gt_hits) or '(none)'}")

print()
print("Pick the variant with the highest GT hit count for the L1 landscape query.")
