# Unified Submission Status Design

**Date:** 2026-05-21  
**Status:** Approved

## Problem

The Grades page has two parallel status systems:
1. `AssessmentGrade.status` (`graded | ungraded | unmapped`) — derived from Blackboard grade data
2. `Assignment.status` (`upcoming | submitted | graded`) — manually managed via a dropdown

When an assignment is submitted to Blackboard but not yet marked, the grade column has no score so it shows `ungraded`, while the assignment dropdown stays on `upcoming` unless the user manually changes it. These get out of sync.

## Solution

Unify into a single status: `upcoming | submitted | graded | unmapped`.  
Status is derived automatically from Blackboard data. The dropdown is removed from the Grades table.

## Unified Status Derivation

Priority order per assessment:

1. BB column has a score → `graded`
2. BB column `bb_status` = `"NeedsGrading"` → `submitted`
3. `assignments.json` `status_override = "submitted"` → `submitted` (manual escape hatch)
4. Otherwise → `upcoming`

`unmapped` = no `column_name` in `assessments.json` (unchanged).

## Data Layer

### `bb_client.py` — `get_column_grade`
Returns `bb_status` alongside `score`:
```python
return {"score": score, "bb_status": data.get("status")}
```

### `grades.py` (syncer)
Writes `bb_status` into each column entry in `grades.json`:
```json
{ "name": "...", "score": null, "possible": 100, "status": "ungraded", "bb_status": "NeedsGrading" }
```
The existing `status` field (`graded|ungraded`) is preserved — grade math is unchanged.

### `assignments.json`
Each assignment gains an optional `status_override` field (default `null`). Only ever set to `"submitted"` manually for paper exams or other cases BB can't detect. Grade sync never writes this field.

## Backend (`app/services/grades.py`)

New helper:
```python
def derive_status(score, bb_status, override) -> str:
    if score is not None: return "graded"
    if bb_status == "NeedsGrading": return "submitted"
    if override == "submitted": return "submitted"
    return "upcoming"
```

`AssessmentGrade.status` gains `"submitted"` as a valid value. Grade calculation math is unchanged — `submitted` is treated identically to `ungraded` for weighted averages.

### Auto-sync of `assignments.json`
After writing `grades.json`, the syncer promotes `Assignment.status` in `assignments.json`:
- `upcoming → submitted` when `bb_status = "NeedsGrading"`
- `upcoming/submitted → graded` when score is present

This keeps the Deadlines and Planner pages accurate without extra work. Never demotes (graded stays graded).

## Frontend

### `types.ts`
`AssessmentGrade.status` gains `'submitted'`. `Assignment.status` and its usages elsewhere are untouched.

### `Grades.tsx`
The `<select>` dropdown is removed from the assessment table rows.  
Score/status cell shows a unified badge:
- `GRADED` + score in green
- `SUBMITTED` in amber (awaiting mark)
- `UPCOMING` dimmed
- `UNMAPPED` as today

### `Grades.module.css`
New `.submitted` badge style (amber, consistent with existing `.graded` / `.ungraded` styles).

## What Does Not Change

- Grade calculation math (weighted averages, first-class tracking)
- `Assignment` model fields other than `status_override` addition
- Deadlines, Planner, and all other pages
- The `status` field in `grades.json` columns (kept for backward compat)
