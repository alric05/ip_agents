# Research Round 2 Findings

## Key Newly Identified High-Relevance Reference
### US12323091B1 (A)
- **Title**: Floating structure for eco-adaptive floating photovoltaic system
- **Priority**: 2025-01-17
- **Why it matters**: This appears to be an *anticipatory* reference matching the invention text nearly verbatim.
- **Key disclosures (from claims/DWPI novelty/abstract)**:
  - Rectangular float with divided top platform and four walls.
  - Cross-shaped support fitting between the walls.
  - Four pontoons held within openings formed by the cross-shaped support.
  - Bifacial PV panel supported via first and second triangular braces.
  - Anchoring via concrete blocks and plastic-coated stainless-steel wires.
  - Environmental monitoring via temperature + irradiance sensors and wireless transmission.

## Additional References Found (semantic / citations)
### Structural / FPV platform (F1/F6 related)
- CN205070913U (B): Multi-combined PV module water floating structure (polygon block + bracket + connecting frame)
- CN205070889U (B): Single group PV module water floating structure (secondary floating unit)
- US20160006391A1 (B): Floating solar PV device with internal lattice forming polygonal cells (modules in cells)
- US20210214056A1 (B): Floatable array ready solar module mounting device (multiple floats + primary frame)
- WO2024078733A1 (B): Floating PV platform with pontoon bodies in groups fixed to metal frame; adjustable PV module angle
- US11319035B2 (B): Floating stage device with central connecting rod and multiple floats on posts (stability)

### Mooring / anchoring (F3 related)
- CN119796426A (B): Floating PV module connected to concrete anchor block via chain/buckle
- US9729101B1 (B): Deployment techniques using mooring buoys + tensioning frame
- IL279932A (B): Floating solar panel array with beams/crossbeams grid and anchoring with geogrid

### Monitoring / telemetry (F4/F5 related)
- CN221138567U (B): Offshore floating PV intelligent monitoring (temperature sensor within protective shell)
- CN207208395U (B): Floating solar device with light sensor on platform
- IN202011046574A (B): IoT monitoring for floating solar; includes voltage/current sensors and wireless nodes

## Coverage Status After Round 2
| Feature | Core? | A-Refs | B-Refs | Level |
|--------|-------|--------|--------|-------|
| F1 Cross-support holding 4 pontoons in a rectangular float | Y | US12323091B1 | JP06564515B1, US20160006391A1, US20210214056A1, WO2024078733A1, CN205070913U | **SATURATED** ✅✅ |
| F2 Triangular supports mounting bifacial PV at tilt | Y | US12323091B1 | CN205430131U, CN105857535A, CN115123472A | **SATURATED** ✅✅ |
| F3 Concrete block + coated stainless wire corner mooring | Y | US12323091B1 | CN119796426A, CN118220409A, CN205632949U | **STRONG** ✅ |
| F4 Top/bottom temp + irradiance sensors + logger + wireless DB | Y | US12323091B1 | IN202011046574A, CN221138567U | **STRONG** ✅ |
| F5 Junction box + current/voltage sensors to logger | N | (implicit in US12323091B1) | IN202011046574A | MODERATE ⚠️ |
| F6 Modular interconnection into arrays | N | (implicit in multiple) | IL279932A, US20210214056A1, CN205070913U | MODERATE ⚠️ |

## Vocabulary / Query Expansion Discovered
- cruciform, cross-shaped support, crossbeam lattice
- pontoon cassette, buoyancy module, floating drum
- deadweight / concrete anchor block, anchor chain buckle
- IoT floating solar monitoring, sensor node, data collector/aggregator

## Notes / Interpretation
- **US12323091B1** is extremely likely to be either (i) the same invention family, or (ii) a directly anticipatory prior art reference. Either way it is critical for novelty risk.
