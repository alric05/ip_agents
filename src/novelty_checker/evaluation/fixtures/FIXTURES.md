# Fixture Pipeline

Converts filled-in **GT Form Excel files** submitted by SMEs into structured fixture directories used by the novelty-checker evaluation framework.

---

## Overview

The fixture pipeline reads each sheet of the GT Form Excel workbook and writes the data out into a set of clean, versioned JSON/YAML/Markdown files — one directory per case. These fixture directories are the ground truth that the evaluation harness compares against the agent's live output. They can be fed directly into the **replay engine**  and the **scorer module** .
`conversion.py` drives all the parsing and writing. `schemas.py` defines Pydantic models for each output file so that every fixture is validated before it hits disk — catching missing fields or unexpected values early. Both files are designed to be extended: new sheets or new output files can be added without touching the rest of the pipeline.

---

## Key Files

| File | Purpose |
|------|---------|
| `conversion.py` | Parses each Excel sheet and writes the fixture files; can be run as a script or imported as a module |
| `schemas.py` | Pydantic models that validate every fixture before it is written |

---

## Output Structure

Each Excel file produces a directory named after its Case ID:

```
fixtures/
└── <case_id>/
    ├── metadata.yaml           # Case info, SME details, time breakdown
    ├── invention_disclosure.md # Full invention description
    ├── gt_features.json        # SME feature decomposition
    ├── gt_references.json      # Blocking prior art + per-feature coverage
    ├── gt_verdict.json         # Final novelty verdict + per-feature risk
    └── gt_search_strategy.json # Databases, queries, vocabulary, CPC/IPC codes
```

---

## How to Run

Place filled-in GT Form Excel files in the `inputs/` folder (or any folder of your choice), then run from the `fixtures/` directory.

### Convert a single GT Form file

```bash
python conversion.py --file "inputs/GT Form - C41662.xlsx"
```

### Convert all GT Form files in a folder

```bash
python conversion.py --folder inputs/
```

### Optional: write fixtures to a custom output directory

```bash
python conversion.py --folder inputs/ --output-dir path/to/output/
```

> By default, fixture directories are written directly inside the `fixtures/` folder (i.e. next to `conversion.py`).

---

## Using as a Module

`conversion.py` can also be imported into other scripts or notebooks for programmatic use:

```python
from conversion import process_file, process_folder

# Single file
process_file("inputs/GT Form - CXXXXX.xlsx")

# Whole folder
process_folder("inputs/")
```

