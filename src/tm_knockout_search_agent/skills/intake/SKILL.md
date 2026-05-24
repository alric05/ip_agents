---
name: intake
description: Validate minimum trademark knockout search intake criteria.
triggers:
  - intake
  - brand name
  - jurisdiction
  - nice class
---

# Intake Skill

Use this skill when the user asks for a trademark or brand knockout screening.

## Required Criteria

Confirm that the user supplied:

- One proposed brand name
- Countries or regional trademark systems
- Nice classes and/or goods/services

Ask only for missing required criteria.

## Clarification Rules

- Support one brand name only in v1.
- If the user says "Europe", ask whether they mean EUIPO or specific countries.
- If the user says "EUIPO" or "European Union", treat that as EUIPO only.
- If goods/services are provided without classes, proceed with class inference
  and document the inference.
- If classes are provided without goods/services, proceed and document limited
  goods context.
- Do not invent missing criteria.
- Default to English unless the user requests another language.

## Output

Produce normalized intake notes suitable for structured artifacts:

- brand_name
- jurisdictions
- regional_systems
- nice_classes
- goods_services
- assumptions
- clarification_questions, if needed
