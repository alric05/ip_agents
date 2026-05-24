# Mode 2: Agent Output Review Instructions

> **Audience:** SMEs who have already submitted a case (disclosure + ground truth) and are now reviewing the AI agent's output for that same case.
>
> **What this is:** After you submitted your invention case in Mode 1, we ran our AI agent on your disclosure. We are now sending you the agent's output so you can identify where it got things right and where it went wrong.
>
> **What you submit:** A filled copy of [SME_MODE2_REVIEW_FORM.md](SME_MODE2_REVIEW_FORM.md) for each case you review.

---

## 1. What You Will Receive

For each case, we will send you the agent's complete session output:

| File | What It Contains |
|------|-----------------|
| `scope.md` | The agent's understanding of the invention scope |
| `features.md` | Feature table: ID, Name, Description, Core?, Keywords |
| `findings/` | Per-round search results (patent, NPL, semantic) |
| `references.md` | Consolidated reference list with A/B/C triage labels |
| `final_report.md` | Full 11-section novelty assessment report |
| `telemetry.json` | Tool call timing and round counts (optional, for context) |

You should read at minimum: **scope.md**, **features.md**, **references.md**, and **final_report.md**. The findings directory is useful for understanding *how* the agent found its references.

---

## 2. Review Protocol (Step by Step)

Work through the agent output in this order. For each step, fill in the corresponding section of the [Mode 2 Review Form](SME_MODE2_REVIEW_FORM.md).

### Step 1: Review the Scope (`scope.md`)

Compare the agent's scope to your own understanding of the invention.

- Did the agent correctly identify the technical field?
- Did it capture the core problem being solved?
- Did it miss any important aspects of the invention, or add scope that shouldn't be there?

**Fill in:** Form Section 1 (Scope Review)

### Step 2: Review the Features (`features.md`)

Compare the agent's feature list to the features you defined in your Mode 1 ground truth.

- Which features did the agent identify correctly? (list the agent's feature IDs)
- Which features from your ground truth did the agent **miss**?
- Did the agent define any features that **don't exist** in the invention (hallucinated features)?
- Did the agent get the **Core vs Non-Core** labels right?

**Fill in:** Form Section 2 (Feature Review)

### Step 3: Review the References (`references.md` + `final_report.md` Feature Matrix)

This is the most detailed step. Compare the agent's reference list and triage labels to yours.

**3a. Triage accuracy:** For references that both you and the agent found, check if the triage labels (A/B/C) agree. Note any where the agent over- or under-triaged.

**3b. Feature coverage accuracy:** For shared A/B references, compare the agent's Y/Y1/N coverage against yours. Note any cells where you disagree.

**3c. Missing references:** List important references from your ground truth that the agent did not find at all. For each, note:
- What triage label it should have (A or B)
- How the agent could have found it (what query, what database)
- Why it matters (what features does it cover?)

**3d. Pin-cite errors:** If the agent provided pin-cites (claim numbers, paragraph numbers), spot-check a few for accuracy.

**Fill in:** Form Section 3 (Reference Corrections)

### Step 4: Review the Report (`final_report.md`)

Read the agent's final report with a critical eye:

- **Hallucinated facts:** Does the report state things about references that aren't true? (e.g., claims a patent discloses a feature it doesn't)
- **Wrong coverage percentages:** Are the coverage numbers in the feature matrix consistent with the actual references?
- **Misleading conclusions:** Does the novelty verdict make sense given the evidence? Would it mislead a patent attorney?
- **Missing sections:** Are any of the 11 expected report sections missing or empty?
- **Verdict comparison:** Compare the agent's overall verdict (novel / partial / not_novel) to yours from Mode 1. Do they agree? If not, note what the agent got wrong.
- **Overall quality rating:** Give the agent an overall quality score (1–5) and add any quality notes about patterns you noticed (e.g., the agent consistently misses a type of reference or feature).

**Fill in:** Form Section 4 (Report Quality Assessment)

---

## 3. Time Expectations

| Difficulty Band | Expected Time |
|----------------|--------------|
| Easy | 1.5–2 hours |
| Medium | 2–3 hours |
| Hard | 3–5 hours |

Mode 2 is faster than Mode 1 because you already know the case — you're comparing, not searching from scratch.

---

## 4. Tips for Effective Review

- **Have your Mode 1 ground truth open side-by-side** with the agent output — this makes comparison much faster
- **Focus on A-level and B-level references** — don't spend time on C-refs unless the agent clearly mis-triaged something important
- **Be specific in corrections** — "Agent said Y for F2 on WO2011003643A1, should be Y1 because the coupling topology differs" is much more useful than "wrong coverage"
- **Note failure patterns** — if the agent consistently misses a type of reference (e.g., Chinese utility models) or a feature type (e.g., material properties), note this in the quality notes

---

## 5. Checklist Before Submission

- [ ] Form Section 1 complete (scope review)
- [ ] Form Section 2 complete (feature review)
- [ ] Form Section 3 complete (reference corrections — triage, coverage, missed refs, pin-cites)
- [ ] Form Section 4 complete (report quality assessment)
- [ ] Case metadata filled in (case ID, your name, date, time spent)
- [ ] Specific examples given for each correction (not just "wrong")
