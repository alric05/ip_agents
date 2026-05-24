# Research Round 1 Findings — EFVP (Floating PV platform)

## Sources run (parallel)
- Keyword precision patent search: executed multiple Innography-style queries, but **no bibliographic record list returned** in tool payload (only query strings/hit-count note). No usable references captured from this path in Round 1.
- Structural combination search: executed combo queries, but **no bibliographic record list returned** in tool payload (only query strings/hit-count note). No usable references captured from this path in Round 1.
- Semantic recall search: returned patent candidates (below).

## A/B/C References Captured (from semantic recall)

### A-level
1. CN205430131U — Water Surface Solar Energy Photovoltaic Panel Array (front leg + rear leg bracket; floating part)
   - Why: fixed-tilt bracket on floating part; close to triangular/A-frame mounting concept.
   - Preliminary feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 Y1

2. CN105857535A — Rigid Solar Energy Photovoltaic Array Surface (front/rear supporting legs on multi-floating platform)
   - Why: fixed-tilt mounting via front/rear legs on floating platform.
   - Feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 Y1

3. JP06564515B1 — Aquatic photovoltaic power generation work float mount frame (rectangular float block with cross-beam)
   - Why: rectangular float block + cross-beam/frame terminology; closest to internal cross/cross-beam framing.
   - Feature map: F1 Y1; F2 N; F3 N; F4 N; F5 N; F6 Y1

4. CN118220409A — Sectional floating photovoltaic anchoring system (anchor block + cable connections)
   - Why: anchor-block-based FPV anchoring; close to deadweight block concept.
   - Feature map: F1 N; F2 N; F3 Y1; F4 N; F5 N; F6 Y1

5. CN205632949U — PV power station mounting platform water floating device (reinforced concrete box body + mooring line)
   - Why: concrete body/mooring line; strong deadweight/concrete mooring semantics.
   - Feature map: F1 N; F2 N; F3 Y1; F4 N; F5 N; F6 N

### B-level
6. CN212766646U — Anchor system for large array water surface floating PV power station (Y-shaped steel wire rope)
   - Feature map: F1 N; F2 N; F3 Y1; F4 N; F5 N; F6 Y1

7. CN212766645U — Water surface floating PV power station flexible system anchor system (wire rope + spring device)
   - Feature map: F1 N; F2 N; F3 Y1; F4 N; F5 N; F6 Y1

8. CN208897268U — Photovoltaic power station constant stress anchoring device (counterweight block + pulley + steel rope)
   - Feature map: F1 N; F2 N; F3 Y1; F4 N; F5 N; F6 N

9. CN119370277A — Floating type offshore PV generation platform (tiled + oblique PV set)
   - Feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 Y1

10. CN115694328A — Marine floating PV platform (adjustable angle via upright post)
   - Feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 N

11. CN217445281U — Semi-submersible PV floating platform (fixing bracket arranged along crossing direction)
   - Feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 Y1

12. CN218368211U — Shallow draft marine floating PV platform (lower frame with multiple floating cylinders)
   - Feature map: F1 Y1; F2 N; F3 N; F4 N; F5 N; F6 Y1

13. CN206808435U — Water floating-type PV power generating device (multiple floating units in grid)
   - Feature map: F1 N; F2 N; F3 N; F4 N; F5 N; F6 Y

14. CN218858654U — Floating PV platform (folding bracket + connecting mechanism between blocks)
   - Feature map: F1 N; F2 Y1; F3 N; F4 N; F5 N; F6 Y1

15. CN104124915B — Solar micro-inverter PV component monitoring system (wireless)
   - Feature map: F1 N; F2 N; F3 N; F4 Y1; F5 Y1; F6 N

16. CN205160467U — Environmental parameter collecting/sending box for PV monitoring (temperature + irradiance)
   - Feature map: F1 N; F2 N; F3 N; F4 Y1; F5 N; F6 N

17. CN108879959A — Real-time PV component monitoring method (wireless nodes; includes voltage)
   - Feature map: F1 N; F2 N; F3 N; F4 Y1; F5 Y1; F6 N

### C-level (background)
18. MY203354A — Data logging assembly for monitoring static/non-static PV system
19. CN222966971U — Low power PV panel temperature measuring device (remote monitoring platform)

## Coverage Status After Round 1
| Feature | Core? | A-Refs | B-Refs | Coverage Level | Notes |
|---------|-------|--------|--------|----------------|------|
| F1 Rectangular float + cross support holding 4 pontoons | Y | JP06564515B1 | CN218368211U | MODERATE | Need a closer hit explicitly showing cross partition creating 4 pontoon bays/openings holding separate pontoons.
| F2 Bifacial PV tilt mount via dual triangular supports | Y | CN205430131U; CN105857535A | CN119370277A; CN115694328A; CN217445281U; CN218858654U | STRONG | Need to verify bifacial specificity (many FPV mounts are for monofacial).
| F3 Corner mooring to concrete blocks with coated steel wires | Y | CN118220409A; CN205632949U | CN212766646U; CN212766645U; CN208897268U | STRONG | Need explicit “concrete block + plastic-coated stainless wire + corner” pin-cites.
| F4 PV + environmental sensor suite with onboard data logger | Y | — | CN104124915B; CN205160467U; CN108879959A | MODERATE | Need floating-specific logger/sensors and/or top+bottom temperature for bifacial.
| F5 Electrical monitoring: junction box + current/voltage sensors | N | — | CN104124915B; CN108879959A | MODERATE | Sufficient as supporting unless tightly claimed.
| F6 Modular array build-out | N | — | Multiple (CN206808435U etc.) | MODERATE | Background is abundant.

## Vocabulary Discovered (for query expansion)
- cruciform frame; cross-beam; orthogonal beams
- pontoon cassette; buoyancy module; float block
- deadweight anchor; sinker block; counterweight block
- corner bridle; Y-shaped steel wire rope
- rear irradiance; albedo sensor; SCADA/telemetry logger

## Round 2 Gap-Fill Focus (next)
- F1 (core): target cruciform/cross partition forming **four** bays/openings each retaining separate pontoons.
- F4 (core): target FPV monitoring with **top and bottom** PV temperature (bifacial) + irradiance + wireless logger to database.

## Note on tooling limitation encountered
Two parallel search paths returned only query strings/hit-count notes without underlying publication records. Subsequent rounds will rely on alternative search tooling/workflows and/or direct lookups once additional publication numbers are identified.
