# Research Round 1 Findings (Keyword + Semantic + Combo)

## Patent Keyword Search Results (patent-researcher)
Unique refs (sampled/curated):
- WO2021022444A1 (A) Double-sided solar module arrangement structure for float base — F3
- US20060225635A1 (A) Floating dock/pontoon modules secured to underside — F2 (partial)
- WO2017057018A1 (B) Float for photovoltaic power generation unit — F1 (broad)
- CN205770043U / CN107351985B (B) FPV anchoring systems — F4 (broad)
- CN206133561U / CN210402694U (B) PV monitoring/telemetry devices — F5 (broad)

## Semantic Search Results (semantic-researcher) — curated high similarity
Key A-level seeds:
- US12401313B1 (A) Pontoon platform supported solar PV system; cross-shaped support; bi-facial panel — F1, F2, F3(partial), F5(partial), F6(partial)
- US12323091B1 (A) Floating solar PV system for marine/aquatic environments; rectangular float + cross-shaped support + bifacial — F1, F2, F3(partial)
- CN218617108U (A) Floating PV buoy fixing concrete block anchor structure — F4
- CN215554000U (A) Water surface PV anchoring system with counterweight block — F4
- CN212766646U (A) Anchor system with Y-shaped steel wire rope and stainless buckle — F4
- CN105958909B (A) Triangular-shaped floating PV mounting frame — F3
- IN201831021341A (A) PV performance device sensing temperature, irradiance, current, voltage + comms — F5, F6

B-level supporting examples:
- CN206481252U (B) Floating solar device with reinforced concrete block + steel cable — F4(partial)
- CN206117563U (B) Water floating PV bracket device with triangular frame/tripod — F3
- CN112737503B (B) PV monitoring with V/I + temperature + sunlight radiation — F5/F6(partial)
- CN204594589U (B) Combiner/junction box monitoring + comms — F5/F6(partial)

## Structural Combination Search (structural-combo-searcher)
High-relevance combo candidates:
- US12323091B1 and US12401313B1 again surfaced as multi-feature (F1+F2+F3)
- CN103979084A (B) Module-type offshore floating box with grid structure + cable — F1+F2(+F4 partial)
- US12483186B2 / EP4267893A1 (B) Modular floating PV arrays with triangular floats supporting PV at angle — F1+F3
- CN114802627B (B) Semi-submersible marine PV platform with corner connecting pieces — F1+F4(partial)

## Coverage Status After Round 1 (provisional; based on titles/abstract snippets)
| Feature | Core? | A-Refs | B-Refs | Level |
|---------|------:|------:|------:|-------|
| F1 Rectangular float w/ divided deck & walls | Y | 1 (US12401313B1/US12323091B1) | 2+ | MODERATE ⚠️ |
| F2 Internal cross-frame retaining 4 pontoons | Y | 1 (US12401313B1/US12323091B1) | 1+ | MODERATE ⚠️ |
| F3 Bifacial PV mounting via triangular supports | Y | 1 (CN105958909B) + 1 bifacial float base (WO2021022444A1) | 2+ | MODERATE ⚠️ |
| F4 Corner mooring w/ concrete blocks & coated SS wires | Y | 3 (CN218617108U, CN215554000U, CN212766646U) | 1+ | STRONG ✅ |
| F5 Dual-side PV temp + irradiance monitoring w/ logger & telemetry | Y | 1 (IN201831021341A; not FPV-specific) | 2+ | MODERATE ⚠️ |
| F6 Junction-box electrical sensing (I,V) | N | 1 (IN201831021341A) | 2+ | MODERATE ⚠️ |

## Vocabulary Discovered
- cross-shaped support; cruciform frame; cross beam
- buoyancy body; float unit; floating block
- gravity/deadweight anchor; counterweight block; anchor block
- bridle; Y-shaped wire rope; wire rope; stainless buckle
- triangular-shaped mounting frame; triangular bracket; tripod bracket
- rear-side/backside temperature; albedo; rear irradiance
- sunlight radiation sensor; data acquisition module; monitoring center; SCADA/cloud gateway
- shunt sensor; combiner box monitoring

## Notes / Next Gaps to Target
- Confirm whether US12401313B1 / US12323091B1 truly disclose: (i) divided top platform; (ii) four walls; (iii) cross creating FOUR openings holding FOUR pontoons; (iv) triangular supports (not just generic mount).
- Strengthen F5 specifically for *dual-side* PV temperature sensing (top + bottom) and irradiance + wireless logger.
