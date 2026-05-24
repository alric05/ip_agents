# Patent Tracking Statistics

**Session**: 20260327_162206_6b166109
**Generated**: 2026-03-27T16:36:56.665334

## Funnel Summary

| Stage | Count | Loss | Loss % |
|-------|-------|------|--------|
| Discovered | 71 | - | - |
| Persisted | 73 | -2 | -2.8% |
| Triaged | 52 | 21 | 28.8% |
| Feature Mapped | 30 | 22 | 42.3% |
| Reported | 16 | 14 | 46.7% |

**Overall Retention**: 16/71 = 22.5%

## Total References Evaluated

_All references returned by search tools, including irrelevant ones not tracked through the pipeline._

| Source | Count |
|--------|-------|
| Citation | 6 |
| Patent | 30 |
| Semantic | 38 |
| **Total** | **74** |

Of these, 71 had valid publication numbers and were tracked through the pipeline.

## By Source

| Source | Discovered | Persisted | Triaged | Mapped | Reported |
|--------|-----------|-----------|---------|--------|----------|
| Patent | 30 | 30 | 30 | 30 | 6 |
| Semantic | 38 | 38 | 22 | 0 | 5 |
| Other | 0 | 2 | 0 | 0 | 5 |
| Citation | 3 | 3 | 0 | 0 | 0 |

## By Round

| Round | Discovered | New Unique |
|-------|-----------|------------|
| 1 | 40 | 40 |
| 2 | 31 | 31 |

## By Triage Level

| Label | Count | Feature Mapped | Reported |
|-------|-------|---------------|----------|
| A | 12 | 7 | 8 |
| B | 30 | 16 | 0 |
| C | 10 | 7 | 1 |
| unknown | 25 | 0 | 7 |

## Lost Patents Detail

### Persisted but NOT Triaged (21)

_Saved to disk but never assigned A/B/C label._

| Publication # | Source Tool | Round |
|--------------|------------|-------|
| IN201831021341A | save_round_findings | 1 |
| US12323091B1 | save_round_findings | 1 |
| CN206056642U | semantic_round_2 | 2 |
| CN117353654A | semantic_round_2 | 2 |
| CN117353655A | semantic_round_2 | 2 |
| KR2601440B1 | semantic_round_2 | 2 |
| CN219394799U | semantic_round_2 | 2 |
| CN207208395U | semantic_round_2 | 2 |
| WO2010064271A2 | semantic_round_2 | 2 |
| GB2608913A | semantic_round_2 | 2 |
| CN206364749U | semantic_round_2 | 2 |
| DE202008006347U1 | semantic_round_2 | 2 |
| CN211183899U | semantic_round_2 | 2 |
| CN207173912U | semantic_round_2 | 2 |
| US4691656A | semantic_round_2 | 2 |
| FR2659058A1 | semantic_round_2 | 2 |
| CN107804438A | semantic_round_2 | 2 |
| US10097131B2 | semantic_round_2 | 2 |
| WO2024078733A1 | citation_round_2 | 2 |
| CN108347220A | citation_round_2 | 2 |
| CN112542985A | citation_round_2 | 2 |

### Triaged but NOT Feature-Mapped (22)

_Labelled but no Y/Y1/N feature coverage assigned. Expected for C-level refs._

| Publication # | Source Tool | Round |
|--------------|------------|-------|
| US12401313B1 | semantic_round_1 | None |
| CN215554000U | semantic_round_1 | None |
| CN212766646U | semantic_round_1 | None |
| CN218617108U | semantic_round_1 | None |
| CN105958909B | semantic_round_1 | None |
| CN206481252U | semantic_round_1 | None |
| CN206117563U | semantic_round_1 | None |
| CN112737503B | semantic_round_1 | None |
| CN204594589U | semantic_round_1 | None |
| CN220281630U | semantic_round_1 | None |
| CN218577985U | semantic_round_1 | None |
| CN218858654U | semantic_round_1 | None |
| CN119611671A | semantic_round_1 | None |
| CN209739292U | semantic_round_1 | None |
| CN114932983A | semantic_round_1 | None |
| CN203504483U | semantic_round_1 | None |
| DE3634102A1 | semantic_round_1 | None |
| CN221316601U | semantic_round_1 | None |
| KR2158200B1 | semantic_round_1 | None |
| CN212605702U | semantic_round_1 | None |
| CN218416326U | semantic_round_1 | None |
| CN104124915A | semantic_round_1 | None |

### Feature-Mapped but NOT Reported (24)

_Had feature mappings but omitted from the final report._

| Publication # | Source Tool | Round |
|--------------|------------|-------|
| WO2017057018A1 | patent_round_1 | None |
| CN110239682A | patent_round_1 | None |
| CN207939436U | patent_round_1 | None |
| CN205770043U | patent_round_1 | None |
| CN107351985B | patent_round_1 | None |
| US20040134405A1 | patent_round_1 | None |
| CN206524815U | patent_round_1 | None |
| CN206133561U | patent_round_1 | None |
| CN210402694U | patent_round_1 | None |
| CN201457703U | patent_round_1 | None |
| CN106656000B | patent_round_1 | None |
| CN205986946U | patent_round_1 | None |
| CN212163269U | patent_round_1 | None |
| JP2013138163A | patent_round_1 | None |
| CN203242650U | patent_round_1 | None |
| US11319035B2 | patent_round_2 | None |
| US9729101B1 | patent_round_2 | None |
| EP4663530A1 | patent_round_2 | None |
| CN206629012U | patent_round_2 | None |
| CN107341566A | patent_round_2 | None |
| CN120200553A | patent_round_2 | None |
| CN107196594B | patent_round_2 | None |
| CN107346955A | patent_round_2 | None |
| CN107465388A | patent_round_2 | None |

## Quality Metrics

- **A-ref retention**: 8/12 = 66.7%
- **B-ref retention**: 0/30 = 0.0%
- **Unexplained A/B losses** (feature-mapped but not reported): 18
