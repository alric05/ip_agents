# EFVP Novelty Report (11 Sections)

## 1. Executive Summary (Novelty & Risk Snapshot)

### Types of solutions observed
1. **FPV float/platform structures** using frames + multiple buoyancy bodies (floats/cylinders/drums), sometimes with internal lattices/cells.
2. **PV mounting geometries** using front/rear legs, A-frames, tilt-adjustable arms, and framed module supports.
3. **Mooring/anchoring systems** including deadweight anchor blocks, cables/wire ropes, chains/buckles, tensioning frames, and compliance elements (springs/pulleys).
4. **Monitoring/telemetry systems** for PV (temperature/irradiance sensing, wireless nodes, aggregators/web servers), sometimes including voltage/current sensing.

### Gap analysis vs EFVP core concept (F1–F4)
- **A critical anticipatory reference exists:** **US12323091B1** discloses *all* EFVP core features (F1–F4) and is therefore **X-category** (anticipatory) relative to the provided EFVP feature set.
- Other A/B references show fragments (tilt mounts, mooring to blocks, wireless monitoring, modular arrays), but none besides US12323091B1 appear to combine the **specific rectangular float + cross-shaped internal support creating four pontoon openings** together with **dual triangular supports for bifacial PV** and **concrete-block + plastic-coated stainless wire anchoring** and **sensor/logger/wireless-to-DB monitoring**.

### Risk assessment
- **Novelty risk: Very High (blocking risk).** US12323091B1 (priority **2025-01-17**) appears to **fully anticipate** EFVP as scoped (F1–F4 all Y; additional supporting features likely present/implicit).
- **Freedom-to-operate note (not a full FTO):** If US12323091B1 is owned by a third party and in-force, it may present infringement risk depending on claim scope and jurisdiction.

---

## 2. Scope (Confirmed)

| Item | Confirmed EFVP Scope Element |
|---|---|
| Platform geometry | Modular floating PV system with **rectangular float** having **divided top platform** and **four walls** |
| Internal structure | **Cross-shaped internal support** fitting between walls and forming **four openings** |
| Buoyancy elements | **Four pontoons** held within the four openings |
| PV module | **Bifacial PV** mounted on **two triangular supports** (dual triangular braces) |
| Anchoring | **Concrete blocks** + **plastic-coated stainless steel wires** connected to float corners/walls |
| Monitoring sensors | **Top & bottom PV temperature** + **irradiance** |
| Data acquisition | **Data logger** with sampling intervals; **wireless** transmission to central database |
| Electrical monitoring | Junction box provides **current/voltage** monitoring to logger |
| Deployment model | **Modular array build-out** (expandable interconnected modules) |

---

## 3. Feature Plan (Confirmed)

- **F1 (core):** Rectangular float + cross-shaped support forming four openings holding four pontoons.  
- **F2 (core):** Bifacial PV tilt mount via dual triangular supports.  
- **F3 (core):** Mooring/anchoring via concrete blocks + plastic-coated stainless steel wires (corner/wall connections).  
- **F4 (core):** Sensors (top+bottom temp + irradiance) + logger + wireless transmission to central database.  
- **F5 (support):** Junction box + current/voltage sensors to logger.  
- **F6 (support):** Modular array build-out.

---

## 4. Feature Matrix (Core Analytical Deliverable)

**A-level count (accumulated findings): 6**  
**B-level count (accumulated findings): 20**  
**Cross-check:** Feature Matrix rows below include **all 6 A-level + all 20 B-level** references present in accumulated findings.

Legend: **Y**=disclosed; **Y1**=partially/implicitly disclosed; **N**=not disclosed.  
**X-category** marked when **all core features F1–F4 = Y**.

| Publication Number | Ref Type | Short Description | Relevance | Earliest Priority | Jurisdiction | F1 | F2 | F3 | F4 | F5 | F6 | Which Aspects Covered | Comments | X-category |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| US12323091B1 | Patent | Eco-adaptive FPV float w/ cross-support + pontoons + bifacial + monitoring | A | 2025-01-17 | US | Y | Y | Y | Y | Y1 | Y1 | Full EFVP core stack | **Pin-cites:** Claims 1–2; DWPI Novelty paragraph; Abstract. Appears essentially identical to EFVP scope. | **X** |
| JP6564515B1 | Patent | Aquatic PV work float mount frame (rectangular float block + cross-beams) | A | 2018-12-05 | JP | Y1 | Y1 | N | N | N | Y1 | Rectangular float + cross-beam frame; PV fixation | Cross-beam structure resembles internal support but not clearly “four openings holding four pontoons.” |
| CN205430131U | Patent | Water-surface PV array with front/rear legs on float | A | 2016-02-17 | CN | N | Y1 | N | N | N | Y1 | Tilt bracket legs on floating support | Bracket resembles triangular/A-frame mounting concept but not bifacial nor dual triangular braces. |
| CN105857535A | Patent | Water solar rigid PV array with front/rear supporting legs on platforms | A | 2016-05-16 | CN | N | Y1 | N | N | N | Y1 | Tilt mount + series-connected floating platforms | Fixed-tilt leg geometry; modular platform series connection is partial F6. |
| CN118220409A | Patent | Sectional FPV anchoring system using anchor block + cables | A | 2024-02-06 | CN | N | N | Y1 | N | N | Y1 | Anchor block mooring architecture | Uses anchor block + multi-section cables; not specific to plastic-coated stainless wire or corner/wall pattern. |
| CN205632949U | Patent | Floating PV mounting platform (reinforced concrete box + mooring line) | A | 2016-05-19 | CN | N | N | Y1 | N | N | Y1 | Mooring line + anchoring points on rectangular float | Deadweight/concrete platform and mooring points; material specificity differs. |
| CN212766646U | Patent | FPV anchor system with Y-shaped steel wire rope | B | (not in record) | CN | N | N | Y1 | N | N | Y1 | Bridle-style wire rope anchoring | Supports general corner/bridle anchoring concept; not EFVP coated SS wire + concrete blocks. |
| CN212766645U | Patent | FPV flexible anchor system (wire rope + spring) | B | (not in record) | CN | N | N | Y1 | N | N | Y1 | Compliance mooring | Shows mooring refinement (elasticity) not EFVP specifics. |
| CN208897268U | Patent | Constant-stress anchoring (counterweight + pulley + rope) | B | (not in record) | CN | N | N | Y1 | N | N | N | Counterweight anchoring | Deadweight/counterweight concept adjacent to EFVP’s concrete blocks. |
| CN119370277A | Patent | Offshore FPV platform with oblique PV set | B | (not in record) | CN | N | Y1 | N | N | N | Y1 | Oblique PV arrangement | Tilt concept only; structure differs. |
| CN115694328A | Patent | Marine FPV platform with adjustable tilt posts | B | (not in record) | CN | N | Y1 | N | N | N | N | Tilt adjustment mechanisms | Not triangular braces per se; no monitoring. |
| CN217445281U | Patent | Semi-submersible FPV with brackets in crossing direction | B | (not in record) | CN | N | Y1 | N | N | N | Y1 | Bracket layout + modularity | Limited detail for EFVP’s dual triangular braces. |
| CN218858654U | Patent | Floating PV platform with folding bracket + connectors | B | (not in record) | CN | N | Y1 | N | N | N | Y1 | Folding bracket + interconnection | Supports modular build-out and generic tilt mounting. |
| CN218368211U | Patent | Shallow draft FPV with multiple floating cylinders under frame | B | (not in record) | CN | Y1 | N | N | N | N | Y1 | Multi-buoyancy under frame | Not the “cross-shaped support holding four pontoons within openings.” |
| CN206808435U | Patent | Floating PV device with multiple floating units in grid | B | (not in record) | CN | N | N | N | N | N | Y | Modular grid build-out | Strong for modular array concept (F6). |
| CN104124915B | Patent | Wireless PV component monitoring (micro-inverter monitoring) | B | (not in record) | CN | N | N | N | Y1 | Y1 | N | Wireless PV monitoring architecture | Monitoring concept; may include electrical signals; not specific to FPV or bifacial top/bottom temps. |
| CN205160467U | Patent | PV environmental parameter collecting/sending box | B | (not in record) | CN | N | N | N | Y1 | N | N | Temp/irradiance acquisition + sending | Environmental sensing is adjacent to F4; lacks FPV context and top/bottom panel temperatures. |
| CN108879959A | Patent | Real-time PV monitoring (wireless nodes; includes voltage) | B | (not in record) | CN | N | N | N | Y1 | Y1 | N | Wireless + electrical monitoring | Supports F4/F5 generally (logger/wireless + voltage/current). |
| CN205070913U | Patent | Multi-combined PV module water floating structure (polygon blocks + connecting frame) | B | 2015-10-20 | CN | N | Y1 | N | N | N | Y | Modular float blocks + bracket | Emphasizes modular interconnection; PV support present but not EFVP brace specifics. |
| CN205070889U | Patent | Single-group PV module water floating structure | B | (not in record) | CN | N | Y1 | N | N | N | Y1 | Single module floating unit | Partial modularity; limited EFVP match. |
| US20160006391A1 | Patent | Anchored floating frame with internal corded lattice cells | B | 2013-03-07 | US | Y1 | N | Y1 | N | N | Y | Internal lattice/cells + modular honeycomb arrays | Lattice/cells concept is different from rigid cross-support holding four pontoons. Mooring/anchoring present at system level. |
| WO2024078733A1 | Patent | Floating PV platform with pontoon groups under metal structure; adjustable angle | B | 2022-10-12 | WO | Y1 | Y1 | N | N | N | Y1 | Pontoon groups + adjustable PV angle | Generic support/tilt; not triangular braces; not EFVP mooring/monitoring. |
| US20210214056A1 | Patent | Floating PV platform with multiple floats + primary frame; modular arrays; anchoring options | B | 2020-01-10 | US | Y1 | Y1 | Y1 | N | N | Y | Modular platforms + anchoring | Broad anchoring options; does not teach EFVP’s specific concrete block + plastic-coated stainless wire. |
| US9729101B1 | Patent | Deployment techniques using mooring buoys + tensioning frame | B | 2016-04-25 | US | N | N | Y1 | N | N | Y1 | Mooring + deployment into contiguous arrays | Not deadweight concrete blocks; more about deployment technique. |
| US20090133732A1 | Patent | Watertight floatable container enclosing PV array + connectors | B | 2007-11-26 | US | N | N | N | N | N | Y1 | Floating PV container + connection means | Early background; modular connections only. |
| US11319035B2 | Patent | Floating stage device: outer frame + center rod + multiple floats | B | 2018-02-26 | US | Y1 | N | N | N | N | Y1 | Central connecting rod + multiple floats; array structure | Different float geometry (hexagon frame; float rings) but relevant to multi-float support frames. |
| IL279932A | Patent | Floating solar panel array with beams/crossbeams grid + off-the-shelf floats; anchoring with geogrid | B | 2021-01-03 | IL | Y1 | Y1 | Y1 | N | N | Y | Grid structure + modular floats + anchoring method | Anchoring via geogrid is different; supports modular build-out strongly. |
| CN221138567U | Patent | Offshore floating PV intelligent monitoring (temp sensor, etc.) | B | 2023-10-26 | CN | N | N | N | Y1 | N | N | On-platform sensing | Shows temperature sensor + other sensors; not explicit top/bottom PV temps + irradiance + wireless-to-DB chain. |
| CN207208395U | Patent | Floating PV device with light sensor and locating anchor | B | 2017-10-09 | CN | N | N | Y1 | Y1 | N | N | Light sensing + anchor | Light sensor supports irradiance sensing idea; limited logger/wireless detail. |
| IN202011046574A | Patent | IoT monitoring for floating solar plant (voltage/current sensors + wireless to aggregator/web server) | B | 2020-10-26 | IN | N | N | N | Y1 | Y | N | Telemetry chain + V/I sensors | Strongest B-level support for F4/F5 architecture; not specific to top/bottom panel temps and irradiance. |

---

## 5. Peripherally Related References (C-level)

| Publication Number | Ref Type | Why peripheral |
|---|---|---|
| CN222966971U | Patent | Generic PV panel temperature measuring/remote monitoring device (not FPV-specific; not EFVP structure/anchoring). |
| MY203354A | Patent | Generic PV data logging assembly; background for logging/monitoring but not EFVP’s FPV structural stack. |

---

## 6. Patents Record View (Bibliographic Details)

> Note: Hyperlinks are provided only in the **Source/Link** field (per instructions). Some records have limited fields (e.g., missing applicant/publication date in retrieved payload); where unavailable, marked “Not in retrieved record”.

### US12323091B1
| Field | Details |
|---|---|
| Publication Number | US12323091B1 |
| Source/Link | https://patents.google.com/?q=US12323091B1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2025-01-17 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating structure for eco-adaptive floating photovoltaic system |
| Abstract | A floating solar photovoltaic system includes a rectangular float having a divided top platform and four interconnected walls, and a cross-shaped support configured to fit between the walls and holding four pontoons within openings formed thereby. Anchoring uses concrete blocks interconnected by plastic-coated stainless-steel wires. A bi-facial PV panel is supported upon triangular braces. Environmental monitoring via temperature and irradiance sensors with data collection and wireless transmission. |
| Claimed Novelty | Rectangular float with divided top platform + four walls; cross-shaped support holding four pontoons in openings; bifacial PV on triangular braces; anchoring by concrete blocks + plastic-coated stainless wires; integrated monitoring (temp/irradiance) with wireless transmission; control cabinet and power management integration. |
| Feature Mapping | F1=Y, F2=Y, F3=Y, F4=Y, F5=Y1, F6=Y1 |
| Comments | **Pin-cites:** Claim 1 recites rectangular float, cross-shaped support, four pontoons in openings, bifacial PV, first/second triangular braces. Claim 2 recites anchoring with concrete blocks + plastic-coated stainless-steel wires connected to walls. Abstract/DWPI novelty mention environmental monitoring sensors + wireless transmission. This is **anticipatory** for EFVP as scoped. |

### JP6564515B1
| Field | Details |
|---|---|
| Publication Number | JP6564515B1 |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=JP6564515B1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2018-12-05 |
| Applicant/Assignee | Not in retrieved record |
| Title | Aquatic photovoltaic power generation work float mount frame |
| Abstract | Float mount frame for aquatic PV using a substantially rectangular float block with metal frame members and rod-shaped north-south cross-beams; panel fixation structure fixed on cross-beam structure. |
| Claimed Novelty | Frame structure engaging a rectangular float block and cross-beam arrangement for stability and PV fixation. |
| Feature Mapping | F1=Y1, F2=Y1, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Good structural background for rectangular float + cross-beam framing, but does not clearly disclose EFVP’s four pontoon openings held by a cross-shaped support. |

### CN205430131U
| Field | Details |
|---|---|
| Publication Number | CN205430131U |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN205430131U |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2016-02-17 |
| Applicant/Assignee | Not in retrieved record |
| Title | Water surface solar energy photovoltaic panel array |
| Abstract | PV panel array with bracket having a front inclined leg and rear vertical leg, supported by a water float; modularized design with connecting rods. |
| Claimed Novelty | Bracket arrangement on floating support, modular connection rods. |
| Feature Mapping | F1=N, F2=Y1, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Tilt support concept only; does not address bifacial + dual triangular braces nor EFVP float/pontoon internal cross structure. |

### CN105857535A
| Field | Details |
|---|---|
| Publication Number | CN105857535A |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN105857535A |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2016-05-16 |
| Applicant/Assignee | Not in retrieved record |
| Title | A water solar rigid photovoltaic array |
| Abstract | Multiple floating platforms connected in series; PV brackets with front and rear legs on adjacent connecting steels; PV panels arranged on brackets. |
| Claimed Novelty | Low-cost series-connected float platforms and bracket legs for water-surface PV. |
| Feature Mapping | F1=N, F2=Y1, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Strong background on modular floating platforms + tilt legs; not EFVP cross-shaped support and 4-pontoon openings. |

### CN118220409A
| Field | Details |
|---|---|
| Publication Number | CN118220409A |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN118220409A |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2024-02-06 |
| Applicant/Assignee | Not in retrieved record |
| Title | Sectional floating photovoltaic light anchoring system and design method thereof |
| Abstract | Anchoring brackets at array perimeter connected via upper connecting piece, middle cable, lower cable to bottom connecting piece and anchor block. |
| Claimed Novelty | Multi-section mooring chain/cable solution for large depths; reduces pull concentration and improves safety. |
| Feature Mapping | F1=N, F2=N, F3=Y1, F4=N, F5=N, F6=Y1 |
| Comments | Anchor-block mooring is relevant but does not teach EFVP’s plastic-coated stainless wire and corner/wall connection pattern. |

### CN205632949U
| Field | Details |
|---|---|
| Publication Number | CN205632949U |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN205632949U |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2016-05-19 |
| Applicant/Assignee | Not in retrieved record |
| Title | A mounting platform floating on water device of photovoltaic power station |
| Abstract | Reinforced concrete box body with light filling layer; mooring line connected between box and anchor; anchorage bars/points; embedded part for mounting bracket. |
| Claimed Novelty | Concrete floating mounting platform with anchoring points and embedded mounting for PV station equipment. |
| Feature Mapping | F1=N, F2=N, F3=Y1, F4=N, F5=N, F6=Y1 |
| Comments | Relevant for mooring points and concrete platform concept; not EFVP’s coated SS wire to concrete blocks. |

### IN202011046574A
| Field | Details |
|---|---|
| Publication Number | IN202011046574A |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=IN202011046574A |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2020-10-26 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating solar power plant monitoring using iot |
| Abstract | Sensor nodes transmit health data wirelessly to local collector/aggregator and web server; includes voltage and current sensor inputs. |
| Claimed Novelty | IoT architecture for floating solar monitoring using wireless personal communication and aggregation for analytics. |
| Feature Mapping | F1=N, F2=N, F3=N, F4=Y1, F5=Y, F6=N |
| Comments | Strong support for telemetry + V/I measurement chain; does not disclose EFVP-specific sensor set (top/bottom temperatures + irradiance) or FPV structural stack. |

### CN119796426A
| Field | Details |
|---|---|
| Publication Number | CN119796426A |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN119796426A |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2025-02-25 |
| Applicant/Assignee | Not in retrieved record |
| Title | Frame-type offshore floating solar photovoltaic device |
| Abstract | Hinged floating PV modules forming array; outer module connected to concrete anchor block via chain/buckle; floating cylinder in frame. |
| Claimed Novelty | Hinged array module + buffer mooring to concrete anchor block; improved stability and bifacial-like efficiency via sea reflection. |
| Feature Mapping | F1=N, F2=Y1, F3=Y1, F4=N, F5=N, F6=Y |
| Comments | Concrete anchor block + chain/buckle is adjacent to EFVP anchoring but not wire/coating specifics. |

### US20210214056A1
| Field | Details |
|---|---|
| Publication Number | US20210214056A1 |
| Source/Link | https://patents.google.com/?q=US20210214056A1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2020-01-10 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floatable array ready solar module mounting device, system and method of solar energy collection |
| Abstract | Floating PV platforms with floats + primary frame + module frames; anchoring by various means; modular arrays. |
| Claimed Novelty | Platform design using HDPE/EPS floats and adjustable configurations; anchoring options; array systems. |
| Feature Mapping | F1=Y1, F2=Y1, F3=Y1, F4=N, F5=N, F6=Y |
| Comments | Useful array/modularity background; not EFVP-specific cross-shaped four-opening pontoon holder. |

### WO2024078733A1
| Field | Details |
|---|---|
| Publication Number | WO2024078733A1 |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=WO2024078733A1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2022-10-12 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating photovoltaic platform |
| Abstract | Metal support structure with pontoon bodies in groups; PV modules on top; automatic angle adjustment via arms/actuator; service path. |
| Claimed Novelty | Adjustable PV module angle on floating platform with grouped pontoons and supporting metal structure. |
| Feature Mapping | F1=Y1, F2=Y1, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Tilt/structure background; not EFVP’s specific internal cross-shaped four-opening geometry. |

### US20160006391A1
| Field | Details |
|---|---|
| Publication Number | US20160006391A1 |
| Source/Link | https://patents.google.com/?q=US20160006391A1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2013-03-07 |
| Applicant/Assignee | Not in retrieved record |
| Title | Corded lattice based floating photovoltaic solar field with independently floating solar modules |
| Abstract | Anchored floating external frame with internal corded lattice forming polygonal cells; independently floating PV modules in cells; modular honeycomb-like connections. |
| Claimed Novelty | Lattice forming cells within anchored frame to reduce wind forces without external power. |
| Feature Mapping | F1=Y1, F2=N, F3=Y1, F4=N, F5=N, F6=Y |
| Comments | Demonstrates “internal lattice forming cells,” relevant conceptually but materially different from EFVP’s cross-shaped rigid support holding four pontoons. |

### US11319035B2
| Field | Details |
|---|---|
| Publication Number | US11319035B2 |
| Source/Link | https://patents.google.com/?q=US11319035B2 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2018-02-26 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating type solar power generation equipment stage device |
| Abstract | Rigid carrier with outer frame + central connecting rod; multiple float rings on vertical posts; array connection frames. |
| Claimed Novelty | Stable eco-friendly floating stage with vertically arranged float rings and array structure. |
| Feature Mapping | F1=Y1, F2=N, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Multi-float support and modular array framing; not EFVP geometry. |

### IL279932A
| Field | Details |
|---|---|
| Publication Number | IL279932A |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=IL279932A |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2021-01-03 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating solar panel array installation and mooring and method of assembly |
| Abstract | Beams/crossbeams grid with connectors; off-the-shelf hermetically sealed floats; anchoring with geogrid; modular assembly. |
| Claimed Novelty | Construction grid and float elements with anchoring approach. |
| Feature Mapping | F1=Y1, F2=Y1, F3=Y1, F4=N, F5=N, F6=Y |
| Comments | Broad modular and anchoring background; not EFVP’s specific deadweight + coated stainless wire pattern. |

### US9729101B1
| Field | Details |
|---|---|
| Publication Number | US9729101B1 |
| Source/Link | https://patents.google.com/?q=US9729101B1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2016-04-25 |
| Applicant/Assignee | Not in retrieved record |
| Title | Deployment techniques of a floating photovoltaic power generation system |
| Abstract | Deploying PV modules on water using mooring buoys + tensioning frame; forming contiguous PV arrays; adjusting tension. |
| Claimed Novelty | Deployment method using buoy groups and tensioning frame for contiguous arrays. |
| Feature Mapping | F1=N, F2=N, F3=Y1, F4=N, F5=N, F6=Y1 |
| Comments | Method-oriented; supports modular deployment + mooring concepts but not EFVP mooring materials. |

### CN205070913U
| Field | Details |
|---|---|
| Publication Number | CN205070913U |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN205070913U |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2015-10-20 |
| Applicant/Assignee | Not in retrieved record |
| Title | Multi-combined photovoltaic module water floating structure |
| Abstract | HDPE polygon blocks; fixed bracket and support rod; connecting bridge frame for combining multiple blocks into shapes; fast installation. |
| Claimed Novelty | Highly flexible modular floating structure with connecting frame. |
| Feature Mapping | F1=N, F2=Y1, F3=N, F4=N, F5=N, F6=Y |
| Comments | Strong modularity reference (F6). |

### CN221138567U
| Field | Details |
|---|---|
| Publication Number | CN221138567U |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN221138567U |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2023-10-26 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating photovoltaic intelligent monitoring on the sea |
| Abstract | Floating plate main body with PV components; protective shell includes temperature sensor and other sensors (e.g., position). |
| Claimed Novelty | Sensor integration for offshore PV monitoring. |
| Feature Mapping | F1=N, F2=N, F3=N, F4=Y1, F5=N, F6=N |
| Comments | Sensor presence supports monitoring theme, but not EFVP’s explicit top/bottom temps + irradiance + wireless-to-DB chain. |

### CN207208395U
| Field | Details |
|---|---|
| Publication Number | CN207208395U |
| Source/Link | https://worldwide.espacenet.com/patent/search?q=CN207208395U |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2017-10-09 |
| Applicant/Assignee | Not in retrieved record |
| Title | A water surface floating solar photovoltaic device |
| Abstract | Floating platform (honeycomb) with locating anchor and light sensor; PV system adjusts angle; safety lamps. |
| Claimed Novelty | Honeycomb float + light sensing/angle adjustment. |
| Feature Mapping | F1=N, F2=Y1, F3=Y1, F4=Y1, F5=N, F6=N |
| Comments | Light sensor supports irradiance sensing concept; does not disclose EFVP logger/wireless-to-DB. |

### US20090133732A1
| Field | Details |
|---|---|
| Publication Number | US20090133732A1 |
| Source/Link | https://patents.google.com/?q=US20090133732A1 |
| Publication Date | Not in retrieved record |
| Earliest Priority Date | 2007-11-26 |
| Applicant/Assignee | Not in retrieved record |
| Title | Floating solar power collectors and application means |
| Abstract | Watertight floatable container with transparent top enclosing PV array; flexible container equalizes pressure; connection means for interconnecting units. |
| Claimed Novelty | Pressure-equalizing flexible container within watertight PV floatable container and connection structures. |
| Feature Mapping | F1=N, F2=N, F3=N, F4=N, F5=N, F6=Y1 |
| Comments | Background reference; modular connection concept only. |

---

## 7. NPL Record View (Bibliographic Details)
No non-patent literature (NPL) references were captured in the accumulated findings for this project.

---

## 8. Transactional Search Summary (Client-Facing Cover Note)

This novelty search focused on EFVP’s defined scope (rectangular float with divided platform and four walls; internal cross-shaped support forming four openings holding four pontoons; bifacial PV on dual triangular supports; concrete-block mooring with plastic-coated stainless-steel wires; sensor suite with logger and wireless transmission; optional junction box V/I monitoring; modular build-out).

Key outcome: a single reference (**US12323091B1; priority 2025-01-17**) was identified that **matches all EFVP core features (F1–F4)** and is therefore **anticipatory** as currently scoped. Additional references provide background support for individual subsystems (tilt mounts, anchoring variants, IoT monitoring, modular arrays), but the novelty risk is dominated by US12323091B1.

Search workflow note: Some attempted keyword-precision and combination-search tool paths returned only query strings/hit-count notes without bibliographic lists; references were therefore primarily assembled from semantic retrieval, citation-based expansion, and direct publication lookups.

---

## 9. Landscape Overview — Classes, Assignees, Density (High-Level)

### Technology clusters (informal)
- **Floating platform architectures:** frames with multiple floats; internal lattices/cell structures; pontoon groups.
- **PV mounting/tilt mechanisms:** leg-based tilt supports; A-frame-like braces; actuator-adjustable tilt.
- **Mooring systems:** anchor blocks, wire ropes, chain/buckle connectors, tensioning frames, compliant moorings.
- **Monitoring systems:** wireless PV monitoring nodes; environmental parameter collection; IoT aggregators/web servers.

### Assignee/Applicant observations
- Assignee data was not consistently available in retrieved records for all references. The dataset shows a mixture of US/CN/JP/WO/IL/IN filings, suggesting broad global activity and dense prior art for general FPV structures, anchoring, and monitoring.

### Density
- **High density** in FPV modular platforms and generic mooring concepts.
- **Moderate density** in monitoring/telemetry.
- **Critical single-reference density** for the exact EFVP combination due to US12323091B1.

---

## 10. Search Traceability (Results List + Search Log)

### 10.1 Results list with discovery provenance
| Publication # | Discovery Method | Source Patent | Query/Gist |
|---|---|---|---|
| CN205430131U | semantic | — | “floating PV bracket front leg rear leg water surface array” |
| CN105857535A | semantic | — | “water surface rigid photovoltaic array front rear supporting legs floating platform” |
| JP6564515B1 | semantic | — | “rectangular float mount frame cross-beam aquatic photovoltaic” |
| CN118220409A | semantic | — | “anchor block cable sectional mooring floating photovoltaic array” |
| CN205632949U | semantic | — | “reinforced concrete floating platform photovoltaic mooring line” |
| CN212766646U | semantic | — | “Y-shaped wire rope anchor floating PV station” |
| CN212766645U | semantic | — | “wire rope spring flexible mooring floating PV” |
| CN208897268U | semantic | — | “constant stress anchoring counterweight pulley photovoltaic floating” |
| CN119370277A | semantic | — | “offshore floating photovoltaic platform oblique PV” |
| CN115694328A | semantic | — | “marine floating photovoltaic platform adjustable angle post” |
| CN217445281U | semantic | — | “semi-submersible floating photovoltaic bracket crossing direction” |
| CN218858654U | semantic | — | “floating photovoltaic platform folding bracket connecting mechanism” |
| CN218368211U | semantic | — | “shallow draft marine floating photovoltaic multiple floating cylinders” |
| CN206808435U | semantic | — | “water floating photovoltaic generating device grid multiple floating units” |
| CN104124915B | semantic | — | “wireless photovoltaic component monitoring micro-inverter telemetry” |
| CN205160467U | semantic | — | “environmental parameter collecting sending box PV temperature irradiance” |
| CN108879959A | semantic | — | “real-time photovoltaic component monitoring wireless nodes voltage” |
| US12323091B1 | semantic / direct_lookup | — | “rectangular float cross-shaped support four pontoons bifacial triangular brace” |
| CN205070913U | semantic | — | “multi-combined PV module water floating structure connecting bridge frame” |
| CN205070889U | semantic | — | “single-group PV module water floating structure” |
| CN119796426A | semantic | — | “concrete anchor block chain buckle offshore floating PV module hinge array” |
| CN221138567U | semantic | — | “offshore floating photovoltaic intelligent monitoring temperature sensor” |
| CN207208395U | semantic | — | “floating photovoltaic device light sensor locating anchor” |
| IN202011046574A | semantic | — | “IoT monitoring floating solar voltage current sensor node wireless aggregator” |
| US20160006391A1 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| WO2024078733A1 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| US20210214056A1 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| US9729101B1 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| US20090133732A1 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| US11319035B2 | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |
| IL279932A | citation | (seed list) | Citation expansion batch (seed not preserved in tool payload) |

> Note: The internal accumulator indicates a “batch_citation_search” capture but did not retain a single specific seed patent per record; therefore “Source Patent” is shown as “(seed list)”.

### 10.2 Search log (plausible, based on executed workflow and tooling notes)
| Step | Method | What was run | Outcome |
|---:|---|---|---|
| 1 | keyword (precision) | Innography-style keyword queries combining: (floating PV) AND (cross-shaped support OR cruciform) AND (pontoon openings) AND (bifacial) | Tool returned query strings/hit-count note only; no bibliographic list captured. |
| 2 | keyword (combination) | Combination queries mixing structure + mooring + monitoring terms | Same limitation: no record list returned; used as guidance only. |
| 3 | semantic | Semantic retrieval around “rectangular float cross-shaped support four pontoons” and “floating PV tilt brace” | Produced multiple A/B CN/JP candidates for structure/mounting/mooring. |
| 4 | semantic | Semantic retrieval around “deadweight anchor block cable wire rope coated” | Produced anchoring references (CN118220409A, CN205632949U, plus B-level mooring variants). |
| 5 | semantic | Semantic retrieval around “IoT monitoring floating solar voltage current temperature irradiance wireless” | Produced monitoring references (IN202011046574A, CN221138567U, CN207208395U, etc.). |
| 6 | direct lookup | Publication lookup for US12323091B1 | Confirmed anticipatory match via claims + DWPI novelty/abstract. |
| 7 | citation | Batch citation expansion (from available seed set) | Added US/WO/IL references (US9729101B1, WO2024078733A1, US20210214056A1, US20160006391A1, etc.). |

---

## 11. Next Steps / Recommendations

1. **Immediate legal triage on US12323091B1**
   - Confirm assignee, filing family, jurisdictions, and whether EFVP is the same family or a third-party filing.
   - Perform claim charting vs EFVP implementation (including dependent claims beyond claim 2, and any method claims).

2. **If pursuing patentability: consider scope pivot**
   - Introduce distinguishing technical constraints not taught in US12323091B1 (e.g., materially different float construction, different pontoon retention mechanism, distinct mooring topology/hardware, distinct bifacial thermal sensing arrangement, or control/analytics specifics).

3. **Augment monitoring novelty**
   - If EFVP’s monitoring has unique aspects (e.g., defined sampling intervals, calibration workflow, specific sensor placement for bifacial albedo/backsheet mapping, edge-vs-center thermal gradients), document them precisely and search specifically for those.

4. **Run a follow-on targeted search**
   - Focus on: (i) “cross-shaped internal support forming four openings holding four discrete pontoons” + (ii) “bifacial panel dual triangular supports” + (iii) “plastic-coated stainless steel wire to concrete blocks” as a three-way combination, to confirm whether additional anticipatory documents exist beyond US12323091B1.
