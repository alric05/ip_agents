# Novelty Assessment Report — Eco-Float Voltaic Platform (EFVP)

## 1. Key Finding / Executive Summary

### Key Finding (Novelty Indication)
**Moderate novelty indication (overall), with notable novelty risk concentrated in the “cross-shaped support retaining four pontoons” and “instrumented bifacial FPV monitoring stack” features.**

- The search found **dense prior art** on:
  - **Floating PV modular raft/platform structures** (e.g., **WO2010064271A2**)
  - **Triangular / angled support frames** for floating PV (e.g., **CN105958909B**, **US12483186B2**)
  - **Deadweight / concrete block anchoring and wire-rope mooring** for FPV (e.g., **CN218617108U**)
  - **Monitoring/telemetry architectures for floating PV (IoT/SCADA/cloud)** (e.g., **IN202011046574A**)
  - **Bifacial measurement concepts** including rear irradiance/albedo (e.g., **US11063556B1**, **CN116192046A**)

- The closest “single-reference” structural matches to EFVP (rectangular float + cross-shaped support + bifacial PV) surfaced as **US12401313B1** and **US12323091B1**, but the available record indicates these are **very late priority** in the feed and therefore are best treated as **confirmatory** rather than strong early novelty-destroying prior art in this assessment.

### Types of Solutions Identified
1. **Modular FPV raft/grid platforms**: raft-like float modules with connectors, walkable surfaces, and tilted panel supports.
2. **Angled/triangular float-based mounts**: float geometry or bracket geometry that inherently sets PV tilt.
3. **Deadweight anchoring systems**: concrete blocks/counterweights with chains/cables/wire rope bridles.
4. **IoT/SCADA monitoring stacks**: local sensor nodes + collector/aggregator + remote server/cloud analytics.
5. **Bifacial performance metrology**: rear irradiance/albedo measurement methods; rear-side (backplate/backsheet) temperature monitoring terminology.

### Gap Analysis Table (Coverage vs. EFVP Core Features)
| Feature | Core? | Coverage Strength | What prior art shows | Remaining differentiator / gap |
|---|---:|---|---|---|
| F1 Rectangular float with divided deck & four walls | Y | **MODERATE** | Many modular FPV rafts/platforms (WO2010064271A2) and framed float platforms (US20210214056A1) | “Divided top platform” + explicit “four walls” configuration not strongly established in earlier refs reviewed |
| F2 Internal cross-shaped support retaining four pontoons | Y | **MODERATE** | Cross-beam / grid / float-retention exists; generic pontoon retention exists (US20060225635A1) | Explicit **cruciform partition** creating **four openings** each holding a **separate pontoon** remained hard to evidence in earlier accessible refs |
| F3 Triangular supports mounting bifacial PV | Y | **MODERATE** | Triangular mounting frames for FPV (CN105958909B) and double-sided-on-float context (WO2021022444A1) | A single earlier ref explicitly combining **bifacial + triangular supports** was not confirmed in retrieved full texts |
| F4 Concrete blocks + plastic-coated stainless wires corner mooring | Y | **STRONG** | Concrete block anchor structures and wire-rope bridle anchoring are well disclosed (CN218617108U; CN212766646U) | “Plastic-coated stainless” appears as a materials optimization; likely an obvious variant of wire rope/cable selection |
| F5 Dual-side PV temperature + irradiance + logger + wireless to central DB | Y | **MODERATE** | IoT monitoring for floating solar incl. V/I sensors and wireless collector to server (IN202011046574A); bifacial irradiance/albedo methods (US11063556B1; CN116192046A); rear-side temperature terminology (CN206056642U) | An explicit **combined stack** (front+rear temps + irradiance/albedo + onboard logger + wireless DB) in one early ref was not confirmed; likely arguable as an integration of known monitoring elements |
| F6 Junction box + current/voltage sensing + telemetry | N | **MODERATE** | Widely known in PV monitoring; explicitly present in floating monitoring architecture (IN202011046574A) | Not a strong novelty lever by itself |

### Technology / Competitor Trends Observed
- **Rapid growth in FPV** modular platforms with interchangeable floats and standardized connections.
- **Anchoring** is a heavily patented area, especially in CN utility models (deadweight blocks, anchor claws, bridle hardware).
- **Monitoring** increasingly uses **IoT nodes + gateway + cloud analytics** (predictive maintenance, data logging).
- **Bifacial-specific monitoring** (rear irradiance/albedo, bifacial gain) is mature at the metrology layer; the FPV-specific integration is emerging.

### Risk Assessment
- **Novelty Risk:** **Medium–High** (because most EFVP elements appear individually in prior art; the key risk depends on whether one earlier reference (or combination) clearly discloses the **cross-shaped 4-pontoon retention** + **bifacial mount** + **monitoring**).
- **Freedom to Operate (FTO) Risk:** **Medium** (anchoring and modular mounts are crowded; concrete anchor/claw designs are particularly dense).
- **Market Opportunity:** **High** (land-constrained regions and waterbody deployment trends support adoption; differentiation may come from manufacturability/modularity + monitoring).

---

## 2. Scope

| Item | Definition |
|---|---|
| Objective | Assess novelty of EFVP floating PV module architecture and associated mooring and monitoring features |
| In-Scope | Modular FPV floats/platform structures; internal cross/cruciform supports retaining multiple pontoons; PV mounting brackets (triangular/A-frame); deadweight/concrete anchoring; PV monitoring (temp/irradiance/I-V) with datalogger and wireless to database |
| Out-of-Scope | PV cell chemistry; inverter/MPPT specifics; choice of wireless protocol; detailed structural engineering calculations |
| Authorities / Data sources | Innography/DWPI-style patent records (keyword + details lookup), NGSP semantic patent retrieval, citation expansion where available |
| Languages | Primarily EN machine translations for CN/WO/EP; some KR/RU surfaced semantically |
| Date range | No explicit limit; older dock/pontoon art considered |
| Assumptions | Module is arrayable; pontoons are insertable; divided deck is a split deck/slot; one bifacial panel per module; telemetry protocol-agnostic |
| Feature Confirmation | User confirmed scope defaults and feature set (F1–F6) |
| Known Constraints | Some precision-search runs returned only hit counts (no record-level bibliographic data), limiting evidence for certain very specific sub-features |

---

## 3. Feature Plan (Confirmed)

| Feature ID | Name | Description | Expected Variations | Core? | Desirable? | Notes |
|---|---|---|---|---:|---:|---|
| F1 | Rectangular float w/ divided deck & walls | Rectangular outer float/frame with four walls and a divided top platform | split deck vs central slot vs segmented panels | Y | Y | Differentiation depends on explicit deck division + walls as claimed |
| F2 | Internal cross-frame retaining 4 pontoons | Cross-shaped support forms four openings holding four pontoons | cruciform bulkhead; X-frame; grid partition | Y | Y | Most differentiating structural detail if truly unique + earlier prior art absent |
| F3 | Bifacial PV mounting via triangular supports | Two triangular supports mount a bifacial PV module at tilt | A-frame; truss; adjustable tilt | Y | Y | Triangular mount is common; bifacial-specific mount less so |
| F4 | Corner mooring w/ concrete blocks & coated SS wires | Deadweight concrete blocks and coated SS cables/wires at corners | chains; wire rope; bridles; helix anchors | Y | N | Crowded area; likely obvious unless special arrangement/material yields unexpected effect |
| F5 | Dual-side PV temp + irradiance + logger & telemetry | Top+bottom temperature + irradiance sensors; logger and wireless to central DB | albedo sensor; rear irradiance; SCADA/cloud; edge devices | Y | Y | Integration around bifacial/FPV may be claimable with specific placements/dataflow |
| F6 | Junction-box I/V sensing + power export | Junction box + current and voltage sensing + cable to load | combiner box; inverter-coupled sensing | N | N | Support feature; generally conventional |

---

## 4. Feature Matrix (Core Analytical Deliverable)

| Publication Number | Ref Type | Short Description | Relevance | Earliest Priority | Jurisdiction | F1 | F2 | F3 | F4 | F5 | F6 | Which Aspects Covered | Comments / Pin-cites | X-category |
|---|---|---|:--:|---|---|:--:|:--:|:--:|:--:|:--:|:--:|---|---|:--:|
| **US20210214056A1** | Patent | FPV platform with multiple floats + primary/module frames; anchoring options | A | 2020-01-10 | US | Y1 | Y1 | Y1 | Y1 | N | N | Modular floating PV frame + floats; anchoring ecosystem | Claims show floats + primary frame + module frame; anchoring options listed in DWPI novelty |  |
| **WO2010064271A2** | Patent | Modular raft-like floating structure for PV array | B | 2008-12-01 | WO | Y | N | Y1 | N | N | N | Modular FPV raft elements + connectors; walkable surface | Claims 1–6: raft-like elements, connecting means, upright bars for tilt |  |
| **US12483186B2** | Patent | Modular FPV with triangular floats supporting tilted PV | A | 2020-12-22 | US | Y1 | N | Y | N | N | N | Triangular float geometry provides panel tilt | Claims 1: “pair of essentially triangular floats…supporting PV array at an angle” |  |
| **CN105958909B** | Patent | Triangular FPV mounting frame with front/rear brackets on buoy base | A | 2016-06-23 | CN | Y1 | N | Y | N | N | N | Triangular bracket system for floating PV mounting | Abstract/Claim 1: front bracket + rear bracket inverted triangle; mounting frame on buoy |  |
| **WO2021022444A1** | Patent | Bifacial/double-sided module arrangement on float base | A | 2019-08-05 | WO | N | N | Y | N | N | N | Double-sided module arrangement structure for float base | Title/abstract level: bifacial on float; needs full text for mount specifics |  |
| **US20060225635A1** | Patent | Floating dock with pontoon modules secured to underside | A | 2005-04-01 | US | N | Y1 | N | N | N | N | Generic retention/attachment of modular pontoons to platform | Background for “retained buoyancy inserts”; not FPV |  |
| **CN218617108U** | Patent | FPV anchor: trapezoidal concrete block with anchor claws + hanging ring | A | 2022-08-26 | CN | N | N | N | Y | N | N | Concrete block deadweight anchor structure for FPV buoy fixing | Claims 1+: concrete block + hanging ring; claws protruding |  |
| **IN202011046574A** | Patent | IoT monitoring for floating solar: sensor nodes w/ V/I + RF modem; aggregator + web server | A | 2020-10-26 | IN | N | N | N | N | Y1 | Y | Monitoring architecture (wireless to server) for FPV | Claim 1: sensor nodes w/ voltage/current sensor + RF modem; aggregator + web server |  |
| **US11063556B1** | Patent | Determine bifacial gain using albedo and backside irradiance | B | (not retrieved) | US | N | N | N | N | Y1 | N | Bifacial metrology (rear irradiance/albedo) | Evidence from semantic snippet; details not pulled in full in this run |  |
| **CN116192046A** | Patent | Monitoring method for double-faced PV measuring front/back irradiance | B | (not retrieved) | CN | N | N | N | N | Y1 | N | Bifacial front/back irradiance measurement | Evidence from semantic snippet |  |
| **CN206056642U** | Patent | Backplate temperature measuring instrument (rear-side temperature terminology) | B | (not retrieved) | CN | N | N | N | N | Y1 | N | Rear-side module temperature measurement concept | Evidence from semantic snippet |  |
| **US12401313B1** | Patent | EFVP-like: cross-shaped support + bifacial panel on floating platform | A | (late/unknown in feed) | US | Y | Y | Y1 | N | Y1 | Y1 | Closest multi-feature structural configuration (as surfaced) | Needs full details lookup to confirm divided deck + 4 walls + 4 openings/4 pontoons |  |
| **US12323091B1** | Patent | EFVP-like: rectangular float + cross-shaped support + bifacial PV | A | (late/unknown in feed) | US | Y | Y | Y1 | N | Y1 | N | Similar to above; confirmatory closeness | Needs full details lookup for the exact “divided deck” + sensor suite + mooring |  |

**Interpretation of X-category:** No single earlier reference in this dataset was confirmed (with accessible full text) to disclose **all** core features F1–F5 simultaneously. The two US B1 references are closest but appear late.

---

## 5. Peripherally Related References (C-level)

| Publication Number | Type | Title | Rationale / Aspects Covered | Note |
|---|---|---|---|---|
| US3779192A | Patent | Modular flotation unit for docks | Background for modular float blocks | Not FPV-specific |
| US20090133732A1 | Patent | Floating solar power collectors | Early floating solar background | Not specific to EFVP architecture |
| WO2014005626A1 | Patent | Floatable solar installation module | Mounting concept on float | Not cross-pontoon retention |
| NL2024967B1 | Patent | Anchoring device for floating solar panel assembly | Anchoring component background | Not core differentiator |

---

## 6. Patents Record View (Bibliographic Details)

### US12483186B2
| Field | Value |
|---|---|
| Publication Number | US12483186B2 |
| Priority Date | 2020-12-22 |
| Jurisdiction | US |
| DWPI Title | Modular floating platform photovoltaic solar arrays… pair of essentially triangular floats… |
| Abstract (key) | Modular unit with PV array supported at an angle by essentially triangular floats and support bars |
| Key claims (salient) | Claim 1: triangular floats with angled upper side supporting PV at an angle; support bars; U-clamps |
| Feature mapping | F1=Y1, F2=N, F3=Y, F4=N, F5=N, F6=N |
| Comments | Strong for triangular/angled float mount; not bifacial-specific in retrieved content |
| Link | https://patents.google.com/?q=US12483186B2 |

### US20210214056A1
| Field | Value |
|---|---|
| Publication Number | US20210214056A1 |
| Priority Date | 2020-01-10 |
| Jurisdiction | US |
| DWPI Title | Platform for floating solar… multiple floats, primary frame, module frame… |
| Abstract (key) | FPV platforms with one or more floats and frames supporting PV modules; platforms may be anchored by various means |
| Key claims (salient) | Claims 1–3: floats + primary frame + module frame; anchored using mooring lines to various anchor points |
| Feature mapping | F1=Y1, F2=Y1, F3=Y1, F4=Y1, F5=N, F6=N |
| Comments | Broad FPV platform + anchoring; lacks EFVP-specific cross-4-pontoon retention and monitoring stack |
| Link | https://patents.google.com/?q=US20210214056A1 |

### WO2010064271A2
| Field | Value |
|---|---|
| Publication Number | WO2010064271A2 |
| Priority Date | 2008-12-01 |
| Jurisdiction | WO |
| DWPI Title | Modular floating structure for photovoltaic installation… raft-like components… connector… |
| Abstract (key) | Floating modular structure for PV installation on water surfaces made of raft-like elements supporting PV panels |
| Key claims (salient) | Claim 1: raft-like elements with connecting means; claims 5–7: walkable surface, upright bars of different heights for tilt |
| Feature mapping | F1=Y, F2=N, F3=Y1, F4=N, F5=N, F6=N |
| Comments | Foundational modular FPV raft prior art |
| Link | https://patents.google.com/?q=WO2010064271A2 |

### CN105958909B
| Field | Value |
|---|---|
| Publication Number | CN105958909B |
| Priority Date | 2016-06-23 |
| Jurisdiction | CN |
| DWPI Title | Triangular-shaped floating photovoltaic power station mounting frame… |
| Abstract (key) | Triangular floating PV installation frame with front/rear brackets on buoy base supporting module mounting frame |
| Key claims (salient) | Claim 1: buoy + bracket base + front/rear brackets inverted triangle + rods + module mounting frame |
| Feature mapping | F1=Y1, F2=N, F3=Y, F4=N, F5=N, F6=N |
| Comments | Strong for triangular bracket/mount design on floating unit |
| Link | https://patents.google.com/?q=CN105958909B |

### CN218617108U
| Field | Value |
|---|---|
| Publication Number | CN218617108U |
| Priority Date | 2022-08-26 |
| Jurisdiction | CN |
| DWPI Title | Floating type photovoltaic buoy fixing anchor structure… trapezoidal concrete block… |
| Abstract (key) | Concrete block anchor with hanging ring and anchor claws protruding; improves wind/wave resistance |
| Key claims (salient) | Claim 1: concrete block + hanging ring + embedded rods + outward/downward claws |
| Feature mapping | F1=N, F2=N, F3=N, F4=Y, F5=N, F6=N |
| Comments | Strong mooring anchor prior art; EFVP’s coated SS wire is likely a routine choice |
| Link | https://patents.google.com/?q=CN218617108U |

### IN202011046574A
| Field | Value |
|---|---|
| Publication Number | IN202011046574A |
| Priority Date | 2020-10-26 |
| Jurisdiction | IN |
| DWPI Title | System for monitoring floating solar power plant using IoT… sensor nodes… wireless… web server |
| Abstract (key) | Sensor nodes transmit health data via wireless to local collector/aggregator and web server for analytics |
| Key claims (salient) | Claim 1: sensor nodes include V/I sensor input + computing unit + RF modem; aggregator + web server |
| Feature mapping | F1=N, F2=N, F3=N, F4=N, F5=Y1, F6=Y |
| Comments | Directly relevant to telemetry/central database aspects; does not require bifacial context |
| Link | https://patents.google.com/?q=IN202011046574A |

---

## 7. Non-Patent Literature (NPL) Record View
No NPL records were returned by the available semantic search runs in this environment (NPL/WoS path did not return citeable articles). This report therefore focuses on patent prior art.

---

## 8. Transactional Search Summary (Client-Facing)

- **Scope:** Floating PV modular platform architecture with cross/pontoon retention, bifacial triangular mounting, concrete-block mooring, and IoT monitoring.
- **Databases/Tools:** Innography/DWPI-style keyword searching; NGSP semantic similarity; limited citation expansion.
- **Method:**
  - Round 1: broad keyword + semantic + combination search
  - Round 2: gap-focused search + citation seeding
  - Round 3: attempted precision search; partial record-return limitation; semantic recall for hardest gaps
  - Full-text lookups performed for key patents to obtain claims/novelty fields.
- **References screened (unique, curated):** ~20 principal records (A/B/C) plus additional non-citeable hit counts.
- **Relevance breakdown (curated):** A ≈ 10, B ≈ 7, C ≈ 4.
- **X-category count:** 0 confirmed (no single earlier ref verified to teach all core features F1–F5).

---

## 9. Landscape Overview (Concise)

### Classes / Themes
- **H02S** (PV supporting structures; monitoring/control)
- Floating structures / pontoons / modular docks (often co-classified in marine/platform classes)
- Anchoring/mooring systems (deadweight blocks, claws, bridles)
- Monitoring and telemetry (IoT nodes, gateways, SCADA/cloud)

### Notable Assignees / Actors (from sampled set)
- Mixed individual inventors and industrial FPV players; CN utility model filings show high density in anchoring.

### Density Indicators
- **High density:** FPV anchoring, modular floats, triangular/tilted mounts
- **Moderate density:** Bifacial-on-water specific mounting
- **Emerging density:** FPV-specific bifacial rear-side monitoring combined with cloud telemetry

---

## 10. Search Traceability (Addendum)

### Results List (Full — curated)
(See Section 4 Feature Matrix and /references.md list in working files.)

### Search Log (Detailed — reconstructed from rounds)
| Stage | Tool/Path | Query ID | Query (summary) | Notes | Status |
|---|---|---|---|---|---|
| R1 | patent-researcher | R1-KW | FPV modular float + cross support + bifacial + mooring + monitoring | Produced initial A/B set incl. WO2021022444A1; CN anchoring refs | Completed |
| R1 | semantic-researcher | R1-SEM | Multi-gist EFVP semantic | Surfaced US12401313B1/US12323091B1; anchoring A-refs; monitoring A-ref candidate | Completed |
| R1 | structural-combo-searcher | R1-COMBO | F1+F2 / F1+F3 / F1+F4 / F3+F5 combos | Surfaced triangular FPV mount families and additional structure refs | Completed |
| R2 | patent-researcher | R2-KW | Gap-focused (F2 four bays; F5 dual-side sensors) | Added US20210214056A1, US12483186B2, etc. | Completed |
| R2 | semantic-researcher | R2-SEM | Gap-focused monitoring + removable buoyancy | Added IN202011046574A, modular FPV raft refs | Completed |
| R2 | citation-researcher | R2-CIT | Citations around A-seeds | Limited useful citations available | Completed |
| R3 | keyword-precision-searcher | R3-PREC | Cruciform four-compartment + bifacial dual-side sensor telemetry | Returned only hit counts in environment | Completed (limited) |
| R3 | semantic-recall-searcher | R3-SEMREC | High recall for F2/F5 specifics | Added CN116192046A, US11063556B1, CN206056642U terms | Completed |
| R4 | get_patent_details | LOOKUPS | Full-text lookups for key refs | Retrieved claims for US12483186B2, US20210214056A1, WO2010064271A2, CN105958909B, CN218617108U, IN202011046574A | Completed |

---

## 11. Next Steps

### Immediate Recommendations (0–2 weeks)
1. **Claim strategy:** Draft independent claims around the **specific structural combination** of:
   - rectangular float with **four walls** + **divided deck**,
   - internal **cross-shaped support** forming **four openings** retaining **four pontoons**,
   - and (optionally) the **triangular supports** for bifacial mounting.
   Keep monitoring/mooring as dependent claims unless you have evidence of unique performance.
2. **Evidence strengthening:** Obtain and review full text for the closest structural A-seeds (**US12401313B1**, **US12323091B1**) to confirm whether they truly anticipate the EFVP configuration (especially divided deck + 4 pontoons retained in 4 openings).

### Optional Extended Search (2–4 weeks)
- Expand searching in **CN/KR/JP** for terms: “cruciform bulkhead”, “four-compartment float”, “buoyancy cassette”, “cross partition wall”, combined with “floating photovoltaic”.
- Run a dedicated NPL search for bifacial FPV monitoring (“rear irradiance”, “albedo”, “backsheet temperature”) to see if standards/papers predate patent filings.

### Monitoring (Watchlist)
- CPC clusters around **H02S20/00** (supporting structures) and **H02S30/00** (monitoring/control), plus floating-structure/mooring classes appearing with FPV.

### Prototype Validation (Engineering)
- Demonstrate quantitative advantages: e.g., stability, assembly speed, pontoon replaceability, bifacial gain improvement, thermal gradient characterization using top/bottom sensors.

### Market / Business Track
- Position as an “eco-adaptive” platform emphasizing modular deployment in land-constrained regions; differentiate by monitoring dataset + operations/maintenance savings.

### Search Quality & Limitations
- **Strengths:** Multi-path strategy (keyword + semantic + combination + citations), plus full-text lookups for representative key patents.
- **Limitations:** Some precision-search paths returned **only hit counts** without record-level data, which may conceal strong F2/F5 prior art; NPL retrieval did not return citeable literature in this environment.
- **QA checklist:**
  - Verified at least one strong prior art family for FPV modular rafts (WO2010064271A2)
  - Verified at least one strong triangular mount ref (CN105958909B; US12483186B2)
  - Verified strong deadweight anchor ref (CN218617108U)
  - Verified FPV IoT monitoring ref (IN202011046574A)

---

# Sources (Key Cited References)
1. WO2010064271A2 — Modular floating structure for photovoltaic array (priority 2008-12-01)
2. CN105958909B — Triangular floating photovoltaic power station installation frame (priority 2016-06-23)
3. US12483186B2 — Floating platform for solar panel arrays (priority 2020-12-22)
4. US20210214056A1 — Floatable array ready solar module mounting device/system (priority 2020-01-10)
5. CN218617108U — Floating photovoltaic buoy fixing anchor structure (priority 2022-08-26)
6. IN202011046574A — Floating solar power plant monitoring using IoT (priority 2020-10-26)
7. WO2021022444A1 — Double-sided solar module arrangement structure for float base (priority 2019-08-05)
8. US20060225635A1 — Floating dock with pontoon modules secured to platform (priority 2005-04-01)
9. CN116192046A — Monitoring of double-faced PV measuring front/back irradiance (semantic surfaced)
10. US11063556B1 — Bifacial gain determination using albedo/backside irradiance (semantic surfaced)
11. US12401313B1 — EFVP-like cross-shaped support + bifacial (semantic surfaced; full text not retrieved here)
12. US12323091B1 — EFVP-like rectangular float + cross-shaped support + bifacial (semantic surfaced; full text not retrieved here)
