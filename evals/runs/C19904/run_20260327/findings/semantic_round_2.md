## Semantic Search Findings - Round 2 (Targeting bifacial FPV backside monitoring + removable cruciform buoyancy inserts)

### Summary
- Searches executed: 10 (5 user-provided gists + 5 follow-up Type F/D gists)
- Unique high/medium similarity candidates reviewed: 200 (20 per query)
- **New, non-duplicate high-value refs curated below**: 20 (emphasis on F1/F2/F3/F5)
- Query types used: Type A, B, C, D, E, **F**
- Key takeaways:
  - **Backside temperature monitoring vocabulary surfaced** ("backplate temperature measuring instrument").
  - **Floating-solar-specific IoT monitoring** surfaced (sensor nodes + local data collector/aggregator).
  - **Removable buoyancy module / detachable buoyancy box** prior art surfaced from dock/pontoon art (strong for F2 removable insert concept).

### References Found (up to 20 new, non-duplicate)
| Publication # | Title (short) | Sim. | Features | Why it matters | Keyword overlap? |
|---|---:|---|---|---|---|
| **IN202011046574A** | Monitoring floating solar power plant using IoT sensor nodes | 1.00 | F5 (F6) | Explicit FPV monitoring architecture: sensor nodes with V/I sensors + computing + RF modem; local data collector/aggregator with Wi‑Fi/RF to remote | Likely UNIQUE |
| **CN206056642U** | PV environment monitoring instrument incl. PV backplate temperature instrument | 0.62 | **F5** | Mentions **photovoltaic assembly backplate temperature measuring instrument** connected to station; strong backside-temp hook | Likely UNIQUE |
| **CN117353654A** | On-site monitoring system for offshore floating photovoltaics | 0.53 | F5 | Offshore FPV monitoring subsystems (environment + array monitoring) | Likely UNIQUE |
| **CN117353655A/B** | RTK-based offshore floating PV intelligent monitoring system | 0.61/0.64 | F5 | Adds **RTK positioning** + data acquisition for floating PV | Likely UNIQUE |
| **KR2601440B1** | LoRa-based real-time monitoring of solar junction box | 0.58 | F5 (F6) | Telemetry term: **LoRa**; junction box status incl. V/I etc. | Partial overlap |
| **CN219394799U** | Measuring PV component power generation in sea-surface floating environment | 0.52 | F5 | FPV measurement system context (sea-surface floating) | Likely UNIQUE |
| **CN207208395U** | Water-surface floating PV device with light sensor | 1.00 | F1 (F5 partial) | Honeycomb floating platform + **light sensor** (irradiance proxy) | Likely UNIQUE |
| **WO2010064271A2** | Modular floating structure for photovoltaic installation | 1.00 | F1 | Modular raft-like float components + connectors; FPV modular network | Overlap possible |
| **GB2608913A** | Modular raft system for floating PV panel installation | 0.70 | F1 | Raft modules + connectors/coupling units | Overlap possible |
| **CN206364749U** | Raft-type PV water-surface floating device | 0.70 | F1, F3 | Net frame + bracket with mounting groove + inclined surface for PV | Overlap possible |
| **DE202008006347U1** | Support system for PV on pontoon-like floating body | 0.72 | F3 (F1) | Clear “pontoon-like floating body” + PV support frame at angle | Overlap possible |
| **IL303565A** | Modular floating platform PV arrays with triangular floats | 0.56 | F3 (F1) | Triangular/angled float bodies giving tilt; alternate triangular-support framing | Likely UNIQUE |
| **CN211183899U** | PV junction box mounting structure for water-surface floating station | 0.77 | F1 (F6) | Floating base box + inclined angle steel frame mounting a junction box | Likely UNIQUE |
| **RU214053U1** | Floating multilayer platform with buoyancy modules connected by clamps | 0.71 | F2 | **Clamped buoyancy modules** suggest removability/replaceability | Likely UNIQUE |
| **CN207173912U** | Water floating platform with floating grid plates | 0.63 | F2 (F1) | “Floating grid plate” vocabulary for modular buoyancy retained by grid | Likely UNIQUE |
| **US4691656A** | Floating dock construction with detachable buoyancy boxes | 0.75 | **F2** | **Detachable buoyancy containers/boxes** on sidewalls; strong removable insert prior art | Likely UNIQUE |
| **FR2659058A1** | Modular pontoon deck with skirt over pneumatic float assembly | 0.62 | F2 (F1) | Deck cavity + subdivided float assembly; modular/removable float vocabulary | Likely UNIQUE |
| **CN107804438A** | Modular offshore working platform with buoyancy chamber cavity + fasteners | 1.00 | F2 (F1) | Buoyancy chamber with cavity structure + fastener connection; possible removable buoyancy module concept | Likely UNIQUE |
| **US10097131B2 / US20190109558A1** | Buoyant platform panel with integrated buoyancy unit + couplers | 0.95/0.54 | F2 | Buoyancy element integrated in panel; joinable modules; good alternative structure | Overlap possible |

### Gap-Filling Results (Round 2 impact)
| Feature | Round 1 Level | Round 2 Evidence Added | Status |
|---|---|---|---|
| F1 Rectangular float w/ divided deck & walls | MODERATE | Modular raft/float docs (WO2010064271A2, GB2608913A, CN206364749U); plus already-known US12401313B1 explicitly has divided platform & walls | ✅ Improving (still verify divided deck in non-US refs) |
| F2 Internal cross-frame retaining 4 pontoons + removable inserts | MODERATE | Detachable buoyancy box art (US4691656A) + clamped buoyancy modules (RU214053U1) + grid plate retention (CN207173912U) | ⚠️ Still need explicit **cruciform** creating **four** compartments with **removable** pontoons |
| F3 Triangular supports for bifacial PV | MODERATE | Pontoon PV support at angle (DE202008006347U1); triangular/angled floats (IL303565A); confirm with existing CN105958909B/WO2021022444A1 | ✅ Improving |
| F5 Dual-side PV temp + irradiance monitoring + wireless logger | MODERATE | FPV IoT monitoring (IN202011046574A); **backplate temperature** instrument (CN206056642U); offshore FPV monitoring systems (CN117353654A/655A) | ⚠️ Still need explicit **rear irradiance** + **front and rear temp** together on FPV |

### ⭐ Vocabulary Discovery (critical for keyword follow-ups)
| Term / phrase | Source | Relevance |
|---|---|---|
| **backplate temperature measuring instrument** | CN206056642U | Direct synonym for backside/rear module temperature sensor |
| **IoT sensor node** / **local data collector and aggregator** | IN202011046574A | FPV-specific distributed monitoring architecture |
| **wireless personal communication** / **RF modem** | IN202011046574A | Telemetry vocabulary beyond “wireless” |
| **LoRa communication** | KR2601440B1 | Common low-power telemetry used in PV monitoring |
| **RTK** (positioning) | CN117353655A/B | Offshore FPV monitoring includes position data |
| **honeycomb structure** floating platform | CN207208395U | Alternate float internal cell/partition wording |
| **detachable buoyancy container/box** | US4691656A | Strong wording for removable buoyancy insert |
| **clamped buoyancy module** | RU214053U1 | Retention mechanism vocabulary for removable pontoons |
| **floating grid plate** | CN207173912U | “Grid” framing for buoyancy-retention structure |
| **raft module / raft-like component / coupling unit** | WO2010064271A2, GB2608913A | Modular FPV raft terminology |

### Suggested follow-up keyword queries (using new vocabulary)
- @(title,abstract,claims) "backplate temperature" NEAR/5 (sensor OR instrument OR measuring)
- @(title,abstract,claims) (rear OR backside OR backsheet) NEAR/5 irradiance NEAR/10 (bifacial OR double-sided)
- @(title,abstract,claims) "IoT" NEAR/5 (floating photovoltaic OR floating solar) NEAR/10 (sensor node OR data collector)
- @(title,abstract,claims) LoRa NEAR/10 (junction box OR combiner box) NEAR/10 photovoltaic
- @(title,abstract,claims) (detachable OR replaceable OR removable) NEAR/5 (buoyancy box OR buoyancy module OR pontoon) NEAR/10 (grid OR lattice OR cruciform OR cross partition)
- @(title,abstract,claims) (cruciform OR cross-shaped OR X-shaped) NEAR/10 (bulkhead OR partition OR compartment) NEAR/10 (four OR 4)
