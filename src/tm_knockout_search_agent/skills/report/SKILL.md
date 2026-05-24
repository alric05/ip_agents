---
name: report
description: Generate the trademark knockout report from structured artifacts.
triggers:
  - report
  - final
  - recommendation
---

# Report Skill

Use this skill after deterministic stopping rules allow finalization.

## Source Of Truth

JSON artifacts are the source of truth. Markdown is the human-readable output.

## Before Writing

Run adversarial review:

- Were all requested countries/systems searched or failures documented?
- Were all classes and goods/services considered?
- Are high-risk conclusions supported by evidence?
- Did low-risk conclusions ignore any strong conflicts?
- Were famous or large-owner concerns considered?
- Are source failures and limitations explicit?
- Does the report follow the template?

## Report Sections

Use this structure:

1. Executive Summary
2. Search Scope
3. Source Coverage
4. Strongest Candidate Findings
5. Country/System Notes
6. Risk Assessment
7. Limitations
8. Disclaimer

Surface only the strongest relevant findings. If no relevant conflicts are
found, say the brand may be shortlisted for deeper legal review subject to
limitations.

## Disclaimer

Use this exact disclaimer:

This is a preliminary trademark screening report for internal triage. It is not
a legal opinion, clearance opinion, or filing recommendation. A qualified
trademark professional should review official records, marketplace evidence,
and jurisdiction-specific law before any adoption or filing decision.
