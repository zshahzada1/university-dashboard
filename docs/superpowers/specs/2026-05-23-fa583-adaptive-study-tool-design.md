# FA583 Adaptive Pomodoro Study Tool — Design Spec

**Date:** 2026-05-23
**Exam:** FA583 Financial Accounting & Reporting — 1 June 2026 (9 days away)
**Status:** Approved — ready for implementation

---

## Problem

The existing `FA583_Exam_Mastery.html` is a well-structured passive reference document. The user falls asleep reading it. His learning method is write-to-learn: copying and rewriting forces recall. The current doc has no mechanism to force that.

---

## Solution

Replace the file in place with a self-contained adaptive Pomodoro write-to-learn tool. Same path, no build step, no external runtime dependencies (one Google Font CDN call is acceptable). All state in localStorage. Works fully offline once loaded.

---

## Architecture

**Single HTML file** with inline CSS + JS. Three views (Sprint / Dashboard / Reference) toggled by CSS. No SPA framework. Vanilla JS only.

**Key components:**
1. `CARDS[]` — static JS array, all cards extracted from source (~197 cards across 15 topics)
2. State manager — loads/saves `fa583_state_v1` to localStorage
3. Leitner engine — adaptive scheduler, boxes 0–5
4. Grading engine — keyword fuzzy match, numeric ±tolerance, MCQ exact, self-grade
5. Sprint controller — timer, queue builder, card loop
6. Dashboard controller — mastery bars, weakest card list, heatmap
7. Reference renderer — read-only theory by topic

---

## Card Schema

```js
{
  id: "ias16-cost-1",           // topic-slug + index
  topic: "IAS 16",              // one of 17 topics
  type: "cloze"|"mcq"|"calc"|"proforma"|"self-grade"|"type",
  priority: false,              // true for the 12 priority facts in s15
  prompt: "...",
  answer: "..."|[...],          // string or array of blank strings (cloze)
  acceptableKeywords: [...],    // for cloze/type: all must appear
  options: [...],               // mcq only
  tolerance: 0.01,              // calc only
  explain: "...",               // shown after attempt
  sourceRef: "Session 2, Test Q1"
}
```

**17 topics (as named in the spec):** Conceptual Framework, IAS 16, IAS 23/40/20, IAS 36/IFRS 5, IAS 2, IAS 37/IAS 10, IAS 38, IFRS 16, Q1 Prep, Q2 Tax, Q4 Consol, IAS 7, MCQ Q3, MCQ Q5, MCQ Harder — drawn from s0–s15 of the source.

**Estimated card counts by type:**
| Topic | cloze | mcq | calc | proforma | self-grade | Total |
|---|---|---|---|---|---|---|
| Conceptual Framework | 10 | 5 | 0 | 0 | 2 | 17 |
| IAS 16 | 11 | 6 | 3 | 1 | 0 | 21 |
| IAS 23/40/20 | 11 | 6 | 1 | 0 | 0 | 18 |
| IAS 36/IFRS 5 | 7 | 5 | 1 | 0 | 0 | 13 |
| IAS 2 | 6 | 6 | 2 | 0 | 0 | 14 |
| IAS 37/IAS 10 | 7 | 6 | 1 | 0 | 2 | 16 |
| IAS 38 | 6 | 5 | 1 | 0 | 0 | 12 |
| IFRS 16 | 7 | 6 | 3 | 2 | 0 | 18 |
| Q1 Prep | 5 | 6 | 0 | 2 | 2 | 15 |
| Q2 Tax | 7 | 7 | 4 | 2 | 2 | 22 |
| Q4 Consol | 7 | 6 | 4 | 2 | 2 | 21 |
| IAS 7 | 5 | 6 | 2 | 1 | 0 | 14 |
| MCQ Q3 | 0 | 10 | 0 | 0 | 0 | 10 |
| MCQ Q5 | 0 | 10 | 0 | 0 | 0 | 10 |
| MCQ Harder | 0 | 6 | 0 | 0 | 0 | 6 |
| **Total** | | | | | | **~207** |

**12 priority cards** — the s15 "facts that win the most marks" list — marked `priority: true`, front-loaded in early sprints.

---

## Adaptive Engine

**Leitner boxes 0–5:**
- Box 0: due every sprint (new / just failed)
- Box 1–5: review intervals of 1, 2, 4, 8, 16 sprints
- Correct → box += 1. Wrong → box = 0
- Box 5 = mastered; shown only in dedicated review

**Sprint composition (25–30 cards, ~25 min):**
- 60% from Box 0/1 due cards
- 30% from Box 2+ due cards
- 10% random unseen (exploration)
- Focus topic selected: 70% from that topic, rest by inverse mastery weighting
- Priority cards (`priority: true`) always appear in first N sprints until promoted out of box 0

---

## Grading Rules

| Type | Grading |
|---|---|
| cloze / type | Case-insensitive; all `acceptableKeywords` must appear (substring); Levenshtein ≤ 2 fuzzy tolerance on individual keywords |
| calc | Parse to float, compare ± tolerance; "close" = within 2× tolerance (shows as wrong but flagged "close") |
| mcq | Exact option index |
| proforma / self-grade | Always reveal model; three self-grade buttons: Got it (box+1), Close (box stays), Missed (box=0) |

After every answer: animated feedback (<200ms), model answer + explain text + sourceRef. Enter advances.

---

## UI — Three Views

### A. Sprint (default landing)
- "Start 25-min Sprint" button; today's stats above it
- Focus dropdown: Auto (weakest first) | [17 topics] | Priority cards only
- Sprint mode: full-screen single card, hides nav
  - Top strip: countdown 25:00 | card N of ~28 | accuracy% | streak | topic name
  - Card: prompt → typed input (autofocus) or radio buttons (MCQ) → Enter submits
  - Proforma/self-grade: textarea → "Reveal model" → side-by-side → 3 self-grade buttons (keys 1/2/3)
  - ESC → confirm abandon
- End screen: cards seen, accuracy, weakest topic, promoted/demoted counts, "Start another" button

### B. Dashboard
- Mastery bar per topic (0–100%, weighted avg of box levels)
- Top 10 weakest cards + "Drill these now" (5-min mini sprint)
- Streak counter + totals (seen / mastered / in progress)
- 14-day dot heatmap (sprints per day)
- "Reset progress" link with confirmation

### C. Reference
- All source theory + worked examples, browsable by topic, read-only
- "Drill this topic (5 min)" button per topic → focused mini sprint
- No card interactivity — pure reference

---

## Persistence

localStorage key `fa583_state_v1`:
```js
{
  cards: { [id]: { box, nextDue, timesWrong, timesRight, lastSeen } },
  sprintCount: number,
  sessions: [{ date, cards, correct, durationMs, focusTopic }],
  streak: number,
  lastSprintDate: ISO date,
  focusTopic: string | null
}
```

Save after every card answered and at end of sprint.

---

## Visual & UX

- Palette: `#10243d` (deep navy) / `#f4f6f9` (cream) / `#caa53d` (gold accent) — matches existing doc
- Typography: Inter via Google Fonts CDN + system font stack fallback
- Sprint mode: high contrast, minimal chrome, card IS the screen
- Mobile-responsive: 320px min; one-handed usable on phone
- Keyboard-first: Enter = submit/advance, 1/2/3 = self-grade, ESC = abandon
- Accessible: input labels, visible focus rings, ✓/✗ icons (not colour-only)
- Subtle animations only, no gimmicks

---

## Constraints

- Single HTML file, inline CSS + JS, target ≤300KB
- No external API calls, no analytics
- Must not lose any factual content — every fact is either a card or in Reference

---

## Acceptance Test

1. Open file → Dashboard shows 0 sprints, full card inventory (~207 cards)
2. Start Sprint → card appears, timer counting down
3. Wrong answer → red feedback, card box → 0
4. Correct answer → green, advance, card box → 1
5. ESC → confirm → returns to landing
6. Reload → progress persisted
7. Second sprint → previously-wrong card resurfaces in first 5

---

## Output

**Replace in place:** `/home/zozo/University/FA583/FA583_Exam_Mastery.html`
