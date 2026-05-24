# Mode 2 Review Form

> Copy this file for each case you review. Filename: `M2-{case_id}.md`
>
> For instructions on how to fill this in, see [SME_MODE2_REVIEW_INSTRUCTIONS.md](SME_MODE2_REVIEW_INSTRUCTIONS.md).

---

## Case Metadata

| Field | Value |
|-------|-------|
| Case ID | |
| Reviewer Name | |
| Review Date | _YYYY-MM-DD_ |
| Time Spent (minutes) | |

---

## 1. Scope Review

| Question | Answer |
|----------|--------|
| Did the agent correctly identify the technical field? | _Y / N_ — |
| Did the agent capture the core problem being solved? | _Y / N_ — |
| Did the agent miss or add scope that shouldn't be there? | _Y / N_ — |
| Scope corrections needed (if any N above) | |

---

## 2. Feature Review

| Action | Details |
|--------|---------|
| Features agent identified correctly | |
| Features agent missed (add these) | |
| Features agent hallucinated (remove these) | |
| Features with wrong core/non-core label | |

---

## 3. Reference Corrections

### 3.1 References with wrong triage

| Ref ID | Agent Triage | Correct Triage | Reason |
|--------|-------------|----------------|--------|
| | _A / B / C_ | _A / B / C_ | |
| | | | |
| | | | |

### 3.2 References with wrong feature coverage

| Ref ID | Feature | Agent Coverage | Correct Coverage | Reason |
|--------|---------|---------------|-----------------|--------|
| | | _Y / Y1 / N_ | _Y / Y1 / N_ | |
| | | | | |
| | | | | |

### 3.3 References the agent missed entirely

| Ref ID | Triage | How to Find | Why Important |
|--------|--------|-------------|---------------|
| | _A / B_ | | |
| | | | |
| | | | |

### 3.4 Pin-cite errors

| Ref ID | Error Description |
|--------|------------------|
| | |
| | |

---

## 4. Report Quality Assessment

| Question | Answer |
|----------|--------|
| Hallucinated facts in report? | _Y / N_ — |
| Wrong coverage percentages? | _Y / N_ — |
| Misleading conclusions? | _Y / N_ — |
| Missing report sections? | |
| Agent's verdict matches yours? | _Y / N_ — Agent: ___ / Yours: ___ |
| Overall agent quality (1–5) | |
| Quality notes | |

---

## Submission Checklist

- [ ] Case metadata filled in
- [ ] Section 1 complete (scope review)
- [ ] Section 2 complete (feature review)
- [ ] Section 3 complete (reference corrections)
- [ ] Section 4 complete (report quality assessment)
- [ ] Specific examples given for each correction (not just "wrong")
