## Semantic Search Findings - Round 1 (Eco-adaptive Floating PV Platform)

### Summary
- Searches executed: 5 (1 batch set of 6 gists + 4 targeted follow-ups)
- Unique candidates surfaced by batch: 114
- Curated conceptually-similar references returned below: 25
- Query types used: Type A, B, C, D, E (Type F not yet run)
- Overall coverage snapshot (preliminary):
  - F1 rectangular float/divided deck: **MODERATE**
  - F2 cross-frame retaining four pontoons: **MODERATE**
  - F3 triangular supports for bifacial panel: **MODERATE**
  - F4 concrete block + coated wire corner mooring: **STRONG**
  - F5 dual-side temp + irradiance monitoring + wireless logger: **MODERATE**
  - F6 current/voltage sensing in junction box: **MODERATE**

### References Found (curated 25)
| Publication # | Title (short) | Score | Triage | Feature hits | Rationale | Keyword Overlap? |
|---|---|---:|:---:|---|---|---|
| **US12401313B1** | Pontoon platform supported solar PV system… **cross-shaped support**… **bi-facial** panel | 1.00 | **A** | F1 F2 F3 F5 F6 | Closest all-in-one: rectangular float with divided platform + cross-shaped support + bifacial PV | Likely UNIQUE semantic |
| CN220281630U | Offshore floating PV platform with stabilizing mechanism | 1.00 | B | F1 | General floating PV platform frame/body | Likely overlap |
| CN218577985U | Semi-submerged floating PV system with main frame | 0.86 | B | F1 | Rectangular-ish frame / semi-submersible approach | Likely overlap |
| CN218858654U | Floating PV platform with folding bracket on floating block | 0.86 | B | F1 F3 | Folding/tilt bracket on float blocks | Likely overlap |
| CN119611671A | Floating PV platform with **gravity anchor** | 0.83 | B | F1 F4 | Explicit gravity anchor concept for floating PV | Likely overlap |
| CN209739292U | Water surface PV bracket floating platform | 0.81 | C | F1 F3 | Generic bracket+float platform | Likely overlap |
| CN114932983A | Marine floating PV platform with anchoring mechanism | 0.79 | B | F4 | Anchoring mechanism under float | Likely overlap |
| ES1287702U | Modular floating PV platform with adjustable anchor pieces | 0.73 | B | F1 F4 | Modular pontoon + anchoring | Likely overlap |
| CN203504483U | Pontoon-type water surface PV station (beams/rods, balance weight) | 0.83 | B | F1 F2 | Pontoon platform framework members | Likely overlap |
| DE3634102A1 | Floating solar cell pontoon of flexibly joined segments | 0.58 | C | F1 | Early modular solar pontoon | Likely overlap |
| CN221316601U | Water PV floating mounting platform with longitudinal/transverse tubes crossed | 0.43 | C | F1 F2 | Crossed tube frame vocabulary | Likely overlap |
| KR2158200B1 | Floating solar install structure with **triangular bracket** and ball joint hinge | 0.45 | B | F1 F3 | Triangular bracket approach on floating unit | Likely overlap |
| **CN215554000U** | New-type water surface PV anchoring system with **counterweight block** | 1.00 | **A** | F4 | Deadweight/counterweight anchoring with cables | Likely overlap |
| **CN212766646U** | Anchor system… **Y-shaped steel wire rope**… stainless buckle | 0.95 | **A** | F4 | Corner bridle / wire-rope mooring analog | Likely overlap |
| **CN218617108U** | Floating PV buoy fixing **concrete block** anchor structure | 0.90 | **A** | F4 | Concrete deadweight block with attachment hardware | Likely overlap |
| CN206481252U | Foam cement plate floating solar device with reinforced concrete block + steel cable | 0.78 | B | F4 | Concrete block + steel cable connection | Likely overlap |
| CN212605702U | Water PV array bracket, mirror-image inclined mounting | 1.00 | B | F3 | Bracket system for floating water PV | Likely overlap |
| **CN105958909B** | **Triangular-shaped** floating PV power station mounting frame | 0.88 | **A** | F1 F3 | Explicit triangular mounting frame for floating PV | Likely overlap |
| CN206117563U | Water floating PV bracket device with triangular frame/tripod | 0.79 | B | F1 F3 | Triangular frame on floating base | Likely overlap |
| IN201831021341A | PV single-module performance device sensing **temperature, irradiance, current, voltage** + comms | 0.76 | **A** | F5 F6 | Directly matches sensor suite + communications | Likely overlap |
| CN218416326U | PV module temperature coefficient monitoring with temp + radiation + shunt sensing | 0.75 | B | F5 F6 | Includes irradiance + electrical sensing | Likely overlap |
| CN112737503B | PV plant working-state monitoring with V/I + temp + sunlight radiation | 0.70 | B | F5 F6 | Combined sensor suite + monitoring | Likely overlap |
| CN104124915A | Micro-inverter PV component monitoring with wireless communications + center | 0.72 | B | F5 | Wireless monitoring to central station | Likely overlap |
| CN204594589U | Combiner-box PV module real-time temperature monitoring + comms | 0.74 | B | F5 F6 | Junction/combiner integration angle | Likely overlap |

### Gap-Filling Results
| Feature | Before | After | Status |
|---|---|---|---|
| F1 rectangular float/divided deck | NONE | MODERATE | ✅ |
| F2 cross-frame retaining four pontoons | NONE | MODERATE | ✅ |
| F3 triangular supports for bifacial panel | NONE | MODERATE | ✅ |
| F4 concrete block + coated wire corner mooring | NONE | STRONG | ✅ Filled |
| F5 dual-side temp + irradiance + wireless logger | NONE | MODERATE | ✅ |
| F6 current/voltage sensing (junction/combiner) | NONE | MODERATE | ✅ |

### ⭐ Vocabulary Discovery (for improved keyword searching)
Key alternative terms seen/anticipated from surfaced refs:
- **Platform/frame**: rectangular float, divided top platform, modular floating pieces, floating block, buoyancy body, floating cylinder
- **Internal support**: **cross-shaped support**, cruciform, cross beam, transverse/longitudinal tubes crossed, stiffener
- **Pontoons**: buoyancy bodies, float units, floating barrels/cylinders, pontoons
- **Mounting**: **triangular-shaped mounting frame**, triangular bracket, tripod bracket, mirror-image inclined bracket
- **Mooring/anchoring**: gravity anchor, **deadweight/counterweight block**, **anchor block**, concrete block, bridle, Y-shaped wire rope, stainless buckle, anchor chain
- **Monitoring/telemetry**: temperature coefficient monitoring, sunlight radiation sensor, irradiance sensor, data acquisition module, wireless communication module, monitoring center, SCADA/cloud gateway
- **Electrical sensing**: shunt sensor, voltage/current monitoring module, combiner box monitoring, junction box sensing

### Suggested Type-F (cross-pollination) queries for Round 2
Use A-ref titles as new semantic queries:
1) "Pontoon platform supported solar photovoltaic system for deployment in marine and aquatic environments"
2) "Triangular-shaped floating photovoltaic power station mounting frame"
3) "New-type water surface photovoltaic anchoring system with counterweight block"
