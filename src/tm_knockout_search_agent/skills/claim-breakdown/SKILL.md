---
name: criteria-normalization
description: Normalize trademark clearance criteria into searchable inputs.
triggers:
  - goods
  - services
  - classes
  - criteria
---

# Criteria Normalization Skill

Use this skill after intake is complete.

## Normalize

- Brand name: trim whitespace and preserve user-facing capitalization.
- Jurisdictions: normalize country codes/names without expanding regional
  systems.
- Regional systems: preserve EUIPO as EUIPO.
- Nice classes: normalize to numeric strings from 1 to 45.
- Goods/services: preserve user text and remove only accidental whitespace.
- Assumptions: record class inference, limited goods context, source limits,
  language defaults, and user constraints.

## Do Not

- Do not invent goods/services.
- Do not expand "EUIPO" to individual countries.
- Do not treat "Europe" as a valid scope without clarification.
- Do not add provider-specific search syntax.

## Output

Produce `TrademarkSearchCriteria`-compatible data:

- brand_name
- jurisdictions
- regional_systems
- nice_classes
- inferred_classes
- goods_services
- business_context
- assumptions
- requires_clarification
- clarification_reasons
