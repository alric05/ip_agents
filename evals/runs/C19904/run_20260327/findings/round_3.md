# Research Round 3 Findings (Precision + High-recall semantic)

## Keyword Precision Search (keyword-precision-searcher)
**Limitation:** tool returned only per-query hit counts (no record-level publication list/snippets), so no new citeable publications could be harvested from that path in this environment.
Hit counts:
- R3-F2-1 (cruciform + four compartments + pontoon insert): 10
- R3-F2-2 (honeycomb/cellular + removable buoyancy): 7
- R3-F2-3 (cross bulkhead + 4 bays + removable floats): 2
- R3-F5-1 (bifacial + front/rear temp + irradiance/albedo + telemetry/logger): 10
- R3-F5-2 (floating PV + rear-side temp + irradiance + telemetry): 10
- R3-F5-3 (rear irradiance/albedo + bifacial + telemetry): 0

## Semantic Recall Search (semantic-recall-searcher) — citeable refs returned
F2-oriented (buoyancy compartment/retention) candidates:
- CN121001926A (B) Porous pontoon for floatable PV module with **four recesses** to receive floats (multi-bay retention; cruciform partition not explicit)
- KR201604321U (C/B) Pontoon boat with multiple partition walls dividing internal compartments (generic, non-FPV)
- US4691656A (B) Floating dock with detachable buoyancy boxes/containers (generic, non-FPV)
- RU214053U1 (B) Floating platform with buoyancy modules connected by clamps (generic)
- CN107804438A (B) Modular offshore working platform with buoyancy chamber cavity + fasteners (generic)

F5-oriented (bifacial monitoring) candidates:
- CN116192046A (B/A-candidate) Monitoring for double-faced PV measuring **front and back irradiance**
- US11063556B1 (B/A-candidate) Determining bifacial gain by measuring **albedo** and backside irradiance
- CN116232221A (B) Cloud-storage monitoring platform for PV station (cloud/DB, not bifacial-specific)
- CN217240667U (B) PV power monitoring system with two radiation monitoring devices (paired irradiance sensors)

## Structural Combination Search (structural-combo-searcher)
Returned only a few citeable refs with limited abstract evidence:
- CN206629012U / CN106921341A (B) Water dual-sided solar cell power generation system with floating support (bifacial-on-water context; no explicit dual-side sensing)

## Coverage Status After Round 3 (provisional)
| Feature | Core? | Level | Notes |
|---------|------:|-------|------|
| F1 Rectangular float w/ divided deck & walls | Y | MODERATE ⚠️ | Strongest specificity remains in late US A-seeds; earlier modular raft refs exist but deck division/walls unclear |
| F2 Internal cross-frame retaining 4 pontoons | Y | MODERATE ⚠️ | Still missing explicit cruciform 4-bay retention in an early accessible ref; CN121001926A suggests 4 recesses but not cross partition |
| F3 Bifacial PV mounting via triangular supports | Y | MODERATE ⚠️ | Triangular FPV mounting covered; bifacial floating covered; explicit combination remains weak |
| F4 Corner mooring w/ concrete blocks & coated SS wires | Y | STRONG ✅ | Deadweight/concrete block + wire rope bridle anchoring widely disclosed |
| F5 Dual-side PV temp + irradiance monitoring w/ logger & telemetry | Y | MODERATE ⚠️ | Bifacial irradiance/albedo monitoring exists; rear-side temperature monitoring exists; explicit combined stack with telemetry not yet confirmed |
| F6 Junction-box electrical sensing (I,V) | N | MODERATE ⚠️ | Many generic PV monitoring refs cover I/V + comms |

## Round 3 Takeaway
Search indicates likely dense art for bifacial monitoring and for modular float compartmentalization, but this environment did not return record-level details for the most targeted precision queries, limiting confirmatory citations for F2/F5 specificity.
