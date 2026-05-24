## Patent Search Findings - Round 2 (Innography keyword)

### Summary
- Searches executed: 5 (4 keyword iterations + 1 citation expansion)
- Unique references (this round): 23 (A: 4, B: 11, C: 8)  
  *Note: counts exclude Round 1 refs unless re-surfaced.*
- Goal focus: strengthen core gaps F1/F2/F3/F5.
- Outcome: Added stronger FPV platform/frame prior art via citations (US20210214056A1, US11319035B2, US9729101B1, US20090133732A1) and bifacial-on-water families (CN107196594B etc.). Still no clean explicit “cross creates four openings retaining four pontoons” found via keyword in this round; and no single FPV/bifacial reference explicitly combining dual-side (front/back) temp sensors + irradiance/albedo + wireless logger.

### Best References Found (Round 2 incremental)
| Publication # | Title (short) | Rel. | Priority Date | Why it matters | Feature hits (F1-F6) |
|---|---:|:--:|---|---|---|
| **US20210214056A1** | Floatable array-ready solar module mounting device/system | **A** | 2020-01-10 | FPV mounting platform w/ multiple floats + primary frame + module frame (good structural platform prior art) | F1:Y1 F2:Y1 F3:Y1 F4:N F5:N F6:N |
| **US11319035B2** | Floating type solar power generation equipment stage device | **A** | 2018-02-26 | Outer frame + central connecting rod; FPV stage device (structural core) | F1:Y1 F2:Y1 F3:N F4:N F5:N F6:N |
| **US9729101B1** | Deployment techniques of floating PV power generation system | **A** | 2016-04-25 | Highly-cited FPV deployment/tensioning frame/mooring buoy approach | F1:Y1 F2:N F3:N F4:Y1 F5:N F6:N |
| **US12483186B2** | Modular floating PV arrays w/ triangular floats supporting PV at angle | **A** | 2020-12-22 | Explicit triangular floats/angled support concept (mount geometry) | F1:Y1 F2:N F3:Y F4:N F5:N F6:N |
| EP4663530A1 | Float structure w/ top frame + interconnected pontoons + cross beams | B | 2024-06-10 | Pontoons connected to top frame via cross beams/holes (retention concepts) | F1:Y1 F2:Y1 F3:N F4:N F5:N F6:N |
| CN206629012U | Water dual-sided solar cell power generation system (floating support) | B | 2017-03-03 | Bifacial/double-sided PV on water + bracket/focusing element | F1:Y1 F2:N F3:Y1 F4:N F5:N F6:N |
| CN107341566A | PV power generation predicting device w/ field data collection + wireless | B | 2017-06-19 | Wireless data collection architecture for PV (logger/telemetry) | F1:N F2:N F3:N F4:N F5:Y1 F6:Y1 |
| CN120200553A | Offshore FPV safe operation early warning (field sensor system) | B | 2025-01-23 | FPV + “field sensor system” vocabulary; SCADA-like monitoring concept | F1:N F2:N F3:N F4:N F5:Y1 F6:N |
| CN107196594B | PV assembly unit w/ gap between module and floating body + reflector | B | 2017-06-30 | Bifacial-supporting concept (rear-side light via gap + reflector) | F1:Y1 F2:N F3:Y1 F4:N F5:Y1 F6:N |
| CN107346955A | PV assembly unit + water PV generating system (concave pit reflector) | B | 2017-06-30 | Similar to above; FPV/bifacial vocabulary | F1:Y1 F2:N F3:Y1 F4:N F5:Y1 F6:N |
| CN107465388A | Improve water generating double-face PV assembly | B | 2017-08-03 | Double-face PV on water + rail/reflector support ideas | F1:Y1 F2:N F3:Y1 F4:N F5:Y1 F6:N |
| US20090133732A1 | Floating solar power collectors and application means | C | 2007-11-26 | Very early FPV concept (watertight floatable container) | F1:Y1 F2:N F3:N F4:N F5:N F6:N |

### Coverage Status (End of Round 2)
| Feature | Target | Level (est.) | A-Refs | B-Refs | Notes |
|---|---:|---|---:|---:|---|
| F1 Rectangular float w/ divided deck & walls | STRONG | **MODERATE** | 0–1* | 2+ | *US12323091B1 claims divided top platform + four walls but has very late priority (2025). Need older explicit divided-deck/walls confirmation (possibly within US20210214056A1 or other modular FPV platform refs after full-text review).* |
| F2 Internal cross-frame retaining 4 pontoons | STRONG | **MODERATE** | 0 | 1–2 | Still missing explicit “cross creates four openings/bays holding four pontoons”. |
| F3 Triangular supports for bifacial PV | STRONG | **MODERATE** | 1 (CN105958909B from R1) | 2+ | US12483186B2 is strong for triangular support geometry; still need explicit bifacial + triangular/A-frame in same ref.
| F5 Dual-side PV temp + irradiance + logger/telemetry | STRONG | **MODERATE** | 1 (IN201831021341A from R1) | 2+ | Round 2 improved telemetry architecture refs, but still no explicit dual-side temp (front+rear) in an FPV/bifacial ref.

### Recommended Gap-Filling Queries for Next Round (if allowed)
- F2 exact 4-pontoon pocket retention:
  - `@(dwpi_title,dwpi_abstract) ((cruciform OR "cross-shaped") NEAR/5 (partition OR frame) AND (quadrant OR "four openings" OR "four chambers") AND (pontoon OR "buoyancy body" OR float block))`
- F1 divided deck as walkway/slot:
  - `@(dwpi_title,dwpi_abstract) ((floating NEAR/5 photovoltaic) AND (walkway OR gangway OR catwalk OR "central slot" OR "equipment bay") AND (perimeter wall OR sidewall))`
- F5 dual-side sensors in PV monitoring:
  - `@(dwpi_title,dwpi_abstract) (("rear side" OR backside) NEAR/5 (temperature sensor) AND (front OR topside) NEAR/5 (temperature sensor) AND (irradiance OR albedo) AND (wireless OR telemetry OR gateway OR SCADA))`
