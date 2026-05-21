# Unified Submission Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual assignment-status dropdown on the Grades page with a unified `upcoming | submitted | graded | unmapped` badge derived automatically from Blackboard's submission data.

**Architecture:** The Blackboard grade API already returns a `status` field per column (e.g. `"NeedsGrading"` when submitted, awaiting grade). We surface this through the sync script into `grades.json`, derive a unified status in the backend grades service, and replace the dropdown in the frontend with a read-only badge. A post-sync step auto-promotes `assignments.json` statuses so Deadlines/Planner stay accurate.

**Tech Stack:** Python 3.12 (sync + backend), FastAPI, React 19 + TypeScript, Vitest, unittest

---

## File Map

| File | Change |
|---|---|
| `sync/scripts/bb_sync/bb_client.py` | Return `bb_status` from `get_column_grade` |
| `sync/scripts/bb_sync/test_bb_client.py` | New tests for `bb_status` |
| `sync/scripts/bb_sync/grades.py` | Store `bb_status` in grades.json; add `_promote_statuses` |
| `sync/scripts/bb_sync/test_grades_syncer.py` | Updated + new tests for promotion |
| `sync/scripts/bb_sync/config.py` | Add `ASSIGNMENTS_PATH` constant |
| `sync/scripts/bb_sync/__main__.py` | Pass `assignments_path` to both `GradeSyncer` instantiations |
| `backend/app/services/grades.py` | Add `derive_status`; update `find_column`, `compute_module`, `compute_grades`, `load_and_compute` |
| `backend/app/routes/grades.py` | Pass `assignments_path` to `load_and_compute` |
| `backend/tests/test_grades_service.py` | Tests for `derive_status` and `submitted` status |
| `frontend/src/lib/types.ts` | `AssessmentGrade.status` gains `'submitted'|'upcoming'`; `Assignment` gains optional `status_override` |
| `frontend/src/routes/Grades.tsx` | Remove dropdown, add status badge |
| `frontend/src/routes/Grades.module.css` | Add badge styles, remove dropdown styles |

---

## Task 1: `bb_client.py` — expose `bb_status` from `get_column_grade`

**Files:**
- Modify: `sync/scripts/bb_sync/bb_client.py`
- Modify: `sync/scripts/bb_sync/test_bb_client.py`

- [ ] **Step 1: Write the failing tests**

Add to the `TestBlackboardClientGradebook` class in `test_bb_client.py`:

```python
def test_get_column_grade_returns_bb_status(self):
    client = self._make_client()
    with patch.object(client, '_get', return_value={"score": 68.0, "status": "Graded"}):
        grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
    self.assertEqual(grade["bb_status"], "Graded")

def test_get_column_grade_needs_grading_status(self):
    client = self._make_client()
    with patch.object(client, '_get', return_value={"status": "NeedsGrading"}):
        grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
    self.assertIsNone(grade["score"])
    self.assertEqual(grade["bb_status"], "NeedsGrading")

def test_get_column_grade_403_returns_none_bb_status(self):
    client = self._make_client()
    err = requests.HTTPError(response=MagicMock(status_code=403))
    with patch.object(client, '_get', side_effect=err):
        grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
    self.assertIsNone(grade["bb_status"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest test_bb_client.TestBlackboardClientGradebook -v 2>&1 | tail -20
```

Expected: 3 failures with `KeyError: 'bb_status'`

- [ ] **Step 3: Update `get_column_grade` in `bb_client.py`**

Replace the existing `get_column_grade` method:

```python
def get_column_grade(self, course_id: str, column_id: str, user_id: str) -> dict:
    """Returns {score: float|None, bb_status: str|None}."""
    try:
        data = self._get(
            f"/learn/api/public/v2/courses/{course_id}"
            f"/gradebook/columns/{column_id}/users/{user_id}"
        )
        score = data.get("score") or (data.get("displayGrade") or {}).get("score")
        return {"score": score, "bb_status": data.get("status")}
    except requests.HTTPError as e:
        if e.response.status_code in (403, 404):
            return {"score": None, "bb_status": None}
        raise
```

- [ ] **Step 4: Run full test suite to verify**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest test_bb_client -v 2>&1 | tail -20
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard && git add sync/scripts/bb_sync/bb_client.py sync/scripts/bb_sync/test_bb_client.py && git commit -m "feat(sync): expose bb_status from get_column_grade"
```

---

## Task 2: `grades.py` (syncer) — write `bb_status` to grades.json

**Files:**
- Modify: `sync/scripts/bb_sync/grades.py`
- Modify: `sync/scripts/bb_sync/test_grades_syncer.py`

- [ ] **Step 1: Write the failing test**

Add to `test_grades_syncer.py` after the existing tests:

```python
def test_sync_writes_bb_status(self):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        from grades import GradeSyncer
        from bb_client import BlackboardClient
        client = BlackboardClient({"BbRouter": "fake"})
        assessments_path = tmp / "assessments.json"
        assessments_path.write_text(json.dumps(ASSESSMENTS))
        grades_path = tmp / "grades.json"
        syncer = GradeSyncer(client, assessments_path, grades_path)
        with patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565), \
             patch.object(client, 'get_column_grade', side_effect=[
                 {"score": 68.0, "bb_status": "Graded"},
                 {"score": None, "bb_status": "NeedsGrading"},
             ]):
            syncer.sync("_user_1", modules=["FA565"])
        out = json.loads(grades_path.read_text())
        cols = out["FA565"]["columns"]
        self.assertEqual(cols[0]["bb_status"], "Graded")
        self.assertEqual(cols[1]["bb_status"], "NeedsGrading")
```

Also update the existing `test_sync_writes_grades_json` to pass `bb_status` in the side_effect (so it doesn't break):

```python
# In test_sync_writes_grades_json, change side_effect to:
side_effect=[{"score": 68.0, "bb_status": "Graded"}, {"score": None, "bb_status": "NotAttempted"}]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest test_grades_syncer -v 2>&1 | tail -20
```

Expected: `test_sync_writes_bb_status` FAIL, others may error on `KeyError: 'score'` since `get_column_grade` now returns a dict with both keys

- [ ] **Step 3: Update `GradeSyncer.sync` in `grades.py`**

Replace the inner loop body inside `sync()` where column grades are fetched:

```python
for col in columns:
    grade = self._client.get_column_grade(course_id, col["id"], user_id)
    score = grade.get("score")
    bb_status = grade.get("bb_status")
    col_grades.append({
        "name": col["name"],
        "score": score,
        "possible": col.get("possible"),
        "status": "graded" if score is not None else "ungraded",
        "bb_status": bb_status,
    })
```

- [ ] **Step 4: Run all sync tests**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest discover -v 2>&1 | tail -30
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard && git add sync/scripts/bb_sync/grades.py sync/scripts/bb_sync/test_grades_syncer.py && git commit -m "feat(sync): store bb_status in grades.json per column"
```

---

## Task 3: `config.py` + `__main__.py` — wire `assignments_path`

**Files:**
- Modify: `sync/scripts/bb_sync/config.py`
- Modify: `sync/scripts/bb_sync/__main__.py`

- [ ] **Step 1: Add `ASSIGNMENTS_PATH` to `config.py`**

Add after the `GRADES_PATH` constant:

```python
ASSIGNMENTS_PATH = os.environ.get(
    "BB_ASSIGNMENTS_PATH",
    str(Path.home() / "University" / "dashboard" / "backend" / "data" / "assignments.json")
)
```

- [ ] **Step 2: Update imports in `__main__.py`**

Change the config import line to:

```python
from config import BB_BASE_URL, LOCAL_ROOT, local_path_for_course, should_sync_course, MODULE_CODE_RE, ASSESSMENTS_PATH, GRADES_PATH, ASSIGNMENTS_PATH
```

- [ ] **Step 3: Pass `assignments_path` to both `GradeSyncer` instantiations in `__main__.py`**

First instantiation (inside `if args.grades:` block, around line 98):

```python
grade_syncer = GradeSyncer(client, assessments_path, grades_path, assignments_path=Path(ASSIGNMENTS_PATH))
```

Second instantiation (at the end of `main()`, around line 139):

```python
grade_syncer = GradeSyncer(client, assessments_path, grades_path, assignments_path=Path(ASSIGNMENTS_PATH))
```

- [ ] **Step 4: Verify `test_config.py` still passes**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest test_config -v 2>&1 | tail -10
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard && git add sync/scripts/bb_sync/config.py sync/scripts/bb_sync/__main__.py && git commit -m "feat(sync): add ASSIGNMENTS_PATH config and wire to GradeSyncer"
```

---

## Task 4: `grades.py` (syncer) — auto-promote `assignments.json` after sync

**Files:**
- Modify: `sync/scripts/bb_sync/grades.py`
- Modify: `sync/scripts/bb_sync/test_grades_syncer.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_grades_syncer.py`:

```python
ASSIGNMENTS_FOR_PROMOTE = [
    {
        "id": "fa565-task-1",
        "module_code": "FA565",
        "assignment_title": "Task 1",
        "weighting_percent": 40,
        "status": "upcoming",
    }
]


class TestPromoteStatuses(unittest.TestCase):
    def _run_sync(self, grade_side_effects, initial_status="upcoming"):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            client = BlackboardClient({"BbRouter": "fake"})
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            assignments = [{**ASSIGNMENTS_FOR_PROMOTE[0], "status": initial_status}]
            assignments_path = tmp / "assignments.json"
            assignments_path.write_text(json.dumps(assignments))
            syncer = GradeSyncer(client, assessments_path, grades_path,
                                 assignments_path=assignments_path)
            with patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565), \
                 patch.object(client, 'get_column_grade', side_effect=grade_side_effects):
                syncer.sync("_user_1", modules=["FA565"])
            return json.loads(assignments_path.read_text())

    def test_promotes_to_submitted_on_needs_grading(self):
        updated = self._run_sync([
            {"score": None, "bb_status": "NeedsGrading"},
            {"score": None, "bb_status": "NotAttempted"},
        ])
        self.assertEqual(updated[0]["status"], "submitted")

    def test_promotes_to_graded_on_score(self):
        updated = self._run_sync([
            {"score": 72.0, "bb_status": "Graded"},
            {"score": None, "bb_status": "NotAttempted"},
        ])
        self.assertEqual(updated[0]["status"], "graded")

    def test_never_demotes_from_graded(self):
        updated = self._run_sync(
            [
                {"score": None, "bb_status": "NotAttempted"},
                {"score": None, "bb_status": "NotAttempted"},
            ],
            initial_status="graded",
        )
        self.assertEqual(updated[0]["status"], "graded")

    def test_noop_when_no_assignments_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            client = BlackboardClient({"BbRouter": "fake"})
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565), \
                 patch.object(client, 'get_column_grade', side_effect=[
                     {"score": None, "bb_status": "NeedsGrading"},
                     {"score": None, "bb_status": "NotAttempted"},
                 ]):
                syncer.sync("_user_1", modules=["FA565"])
            self.assertTrue(grades_path.exists())
```

- [ ] **Step 2: Run to verify failures**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest test_grades_syncer.TestPromoteStatuses -v 2>&1 | tail -20
```

Expected: all FAIL (GradeSyncer doesn't accept `assignments_path` yet, or `_promote_statuses` doesn't exist)

- [ ] **Step 3: Rewrite `grades.py` with full implementation**

Replace the entire file content:

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from bb_client import BlackboardClient


def _find_col(column_name: str, cols: list[dict]) -> dict | None:
    """Find best-matching column by substring. Prefers scored, then submitted."""
    needle = column_name.lower()
    matches = [c for c in cols if needle in c["name"].lower()]
    if not matches:
        return None
    scored = [c for c in matches if c.get("score") is not None]
    if scored:
        return scored[0]
    submitted = [c for c in matches if c.get("bb_status") == "NeedsGrading"]
    if submitted:
        return submitted[0]
    return matches[0]


def _derive_status(score, bb_status: str | None) -> str:
    if score is not None:
        return "graded"
    if bb_status == "NeedsGrading":
        return "submitted"
    return "upcoming"


class GradeSyncer:
    def __init__(self, client: BlackboardClient, assessments_path: Path,
                 grades_path: Path, assignments_path: Path | None = None):
        self._client = client
        self._assessments_path = assessments_path
        self._grades_path = grades_path
        self._assignments_path = assignments_path

    def sync(self, user_id: str, modules: list[str] | None = None) -> dict:
        assessments = json.loads(self._assessments_path.read_text())
        if modules is not None:
            assessments = {k: v for k, v in assessments.items() if k in modules}

        result: dict = {"synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

        for module_code, module_cfg in assessments.items():
            course_id = module_cfg["course_id"]
            columns = self._client.get_gradebook_columns(course_id)
            if columns is None:
                result[module_code] = {"error": "no gradebook access"}
                continue

            col_grades = []
            for col in columns:
                grade = self._client.get_column_grade(course_id, col["id"], user_id)
                score = grade.get("score")
                bb_status = grade.get("bb_status")
                col_grades.append({
                    "name": col["name"],
                    "score": score,
                    "possible": col.get("possible"),
                    "status": "graded" if score is not None else "ungraded",
                    "bb_status": bb_status,
                })
            result[module_code] = {"columns": col_grades}

        self._grades_path.write_text(json.dumps(result, indent=2))
        if self._assignments_path is not None:
            self._promote_statuses(result)
        return result

    def _promote_statuses(self, grades: dict) -> None:
        if not self._assignments_path or not self._assignments_path.exists():
            return
        assessments = json.loads(self._assessments_path.read_text())
        assignments = json.loads(self._assignments_path.read_text())
        lookup = {
            (a["module_code"], float(a["weighting_percent"])): a
            for a in assignments
        }
        changed = False
        for module_code, module_cfg in assessments.items():
            cols = grades.get(module_code, {}).get("columns", [])
            for a_cfg in module_cfg["assessments"]:
                if not a_cfg.get("column_name"):
                    continue
                col = _find_col(a_cfg["column_name"], cols)
                if col is None:
                    continue
                derived = _derive_status(col.get("score"), col.get("bb_status"))
                key = (module_code, float(a_cfg["weight_percent"]))
                asg = lookup.get(key)
                if asg is None:
                    continue
                current = asg.get("status", "upcoming")
                if derived == "graded" and current != "graded":
                    asg["status"] = "graded"
                    changed = True
                elif derived == "submitted" and current == "upcoming":
                    asg["status"] = "submitted"
                    changed = True
        if changed:
            self._assignments_path.write_text(json.dumps(assignments, indent=2))
```

- [ ] **Step 4: Run all sync tests**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync && ../.venv/bin/python -m unittest discover -v 2>&1 | tail -30
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard && git add sync/scripts/bb_sync/grades.py sync/scripts/bb_sync/test_grades_syncer.py && git commit -m "feat(sync): auto-promote assignments.json status after grade sync"
```

---

## Task 5: backend `grades.py` — `derive_status`, `find_column` update, "submitted"/"upcoming" statuses

**Files:**
- Modify: `backend/app/services/grades.py`
- Modify: `backend/tests/test_grades_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_grades_service.py` after the `find_column` tests:

```python
from app.services.grades import derive_status

# ── derive_status ─────────────────────────────────────────────────────────────

def test_derive_status_graded_when_score():
    assert derive_status(72.0, "Graded") == "graded"

def test_derive_status_submitted_when_needs_grading():
    assert derive_status(None, "NeedsGrading") == "submitted"

def test_derive_status_upcoming_when_not_attempted():
    assert derive_status(None, "NotAttempted") == "upcoming"

def test_derive_status_upcoming_when_no_status():
    assert derive_status(None, None) == "upcoming"

def test_derive_status_override_submitted():
    assert derive_status(None, None, override="submitted") == "submitted"

def test_derive_status_score_beats_override():
    assert derive_status(80.0, "Graded", override="submitted") == "graded"

def test_derive_status_needs_grading_beats_override():
    assert derive_status(None, "NeedsGrading", override="submitted") == "submitted"
```

Also add tests for `submitted` appearing in `compute_module` output:

```python
def test_submitted_status_in_assessment_output():
    cols = [
        {"name": "Task 1 - Group Presentation", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NeedsGrading"},
        {"name": "Task 2 - Analytical Essay", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NotAttempted"},
    ]
    result = compute_module(FA565_CFG, cols)
    statuses = {a["title"]: a["status"] for a in result["assessments"]}
    assert statuses["Task 1"] == "submitted"
    assert statuses["Task 2"] == "upcoming"

def test_override_submitted_in_assessment_output():
    cols = [
        {"name": "Task 1 - Group Presentation", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": None},
        {"name": "Task 2 - Analytical Essay", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": None},
    ]
    result = compute_module(FA565_CFG, cols, overrides={40: "submitted"})
    statuses = {a["title"]: a["status"] for a in result["assessments"]}
    assert statuses["Task 1"] == "submitted"
    assert statuses["Task 2"] == "upcoming"

def test_find_column_prefers_submitted_over_upcoming():
    cols = [
        {"name": "Task 1 - Submission", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NeedsGrading"},
        {"name": "Task 1 - Extension", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NotAttempted"},
    ]
    result = find_column("Task 1", cols)
    assert result["bb_status"] == "NeedsGrading"
```

- [ ] **Step 2: Run to verify failures**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_grades_service.py -v 2>&1 | tail -30
```

Expected: new tests FAIL with `ImportError: cannot import name 'derive_status'`

- [ ] **Step 3: Rewrite `backend/app/services/grades.py`**

Full replacement:

```python
from __future__ import annotations
import json
from pathlib import Path


def classify(grade: float) -> str:
    if grade >= 70: return "First"
    if grade >= 60: return "2:1"
    if grade >= 50: return "2:2"
    if grade >= 40: return "Third"
    return "Fail"


_VARIANT_KEYWORDS = frozenset(("extension", "lsp", "referral", "deferral"))


def derive_status(score, bb_status: str | None, override: str | None = None) -> str:
    """Derive unified assessment status from BB data and optional manual override."""
    if score is not None:
        return "graded"
    if bb_status == "NeedsGrading":
        return "submitted"
    if override == "submitted":
        return "submitted"
    return "upcoming"


def find_column(column_name: str, columns: list[dict]) -> dict | None:
    if not column_name:
        return None
    needle = column_name.lower()
    matches = [c for c in columns if needle in c["name"].lower()]
    if not matches:
        return None
    graded = [c for c in matches if c.get("score") is not None]
    if graded:
        return graded[0]
    submitted = [c for c in matches if c.get("bb_status") == "NeedsGrading"]
    if submitted:
        return submitted[0]
    primary = [c for c in matches if not any(kw in c["name"].lower() for kw in _VARIANT_KEYWORDS)]
    return primary[0] if primary else matches[0]


def compute_module(module_cfg: dict, raw_columns: list[dict],
                   overrides: dict | None = None) -> dict:
    assessments_cfg = module_cfg["assessments"]
    weights_sum = sum(a["weight_percent"] for a in assessments_cfg)

    assessments_out = []
    graded_items: list[tuple[float, float]] = []
    ungraded_weight = 0.0

    for a in assessments_cfg:
        w_frac = a["weight_percent"] / 100
        if not a["column_name"]:
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": None, "status": "unmapped",
            })
            continue
        col = find_column(a["column_name"], raw_columns)
        score = col.get("score") if col else None
        bb_st = col.get("bb_status") if col else None
        override = (overrides or {}).get(a["weight_percent"])
        status = derive_status(score, bb_st, override)

        if status == "graded":
            possible = col.get("possible") or 100.0
            mark = score / possible * 100
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": round(mark, 1), "status": "graded",
            })
            graded_items.append((mark, w_frac))
        else:
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": None, "status": status,
            })
            ungraded_weight += w_frac

    if not graded_items:
        return {
            "name": module_cfg["name"], "credits": module_cfg["credits"],
            "grade_so_far": None, "classification": None,
            "needed_for_first": None, "first_status": "possible",
            "weights_ok": abs(weights_sum - 100) < 0.01,
            "assessments": assessments_out,
        }

    graded_weight = sum(w for _, w in graded_items)
    grade_so_far = sum(m * w for m, w in graded_items) / graded_weight

    G = sum(m * w for m, w in graded_items)
    R = ungraded_weight

    if R == 0:
        first_status = "final"
        needed_for_first = None
    else:
        needed = (70 - G) / R
        if needed <= 0:
            first_status = "secured"
            needed_for_first = 0.0
        elif needed > 100:
            first_status = "impossible"
            needed_for_first = round(needed, 1)
        else:
            first_status = "possible"
            needed_for_first = round(needed, 1)

    return {
        "name": module_cfg["name"],
        "credits": module_cfg["credits"],
        "grade_so_far": round(grade_so_far, 1),
        "classification": classify(grade_so_far),
        "needed_for_first": needed_for_first,
        "first_status": first_status,
        "weights_ok": abs(weights_sum - 100) < 0.01,
        "assessments": assessments_out,
    }


def compute_grades(assessments_cfg: dict, grades_raw: dict,
                   overrides: dict | None = None) -> dict:
    synced_at = grades_raw.get("synced_at")
    modules_out: dict = {}
    excluded: list[str] = []
    eligible: list[tuple[float, int]] = []
    total_nonerror_credits = 0

    for code, mcfg in assessments_cfg.items():
        raw = grades_raw.get(code, {})
        if "error" in raw:
            modules_out[code] = {"error": raw["error"]}
            excluded.append(code)
            continue
        total_nonerror_credits += mcfg["credits"]
        mod = compute_module(mcfg, raw.get("columns", []), (overrides or {}).get(code))
        modules_out[code] = mod
        if mod["grade_so_far"] is not None:
            eligible.append((mod["grade_so_far"], mcfg["credits"]))

    if not eligible:
        overall = {
            "grade": None, "classification": None,
            "needed_for_first": None, "first_status": "possible",
        }
    else:
        eligible_credits = sum(c for _, c in eligible)
        weighted_sum = sum(g * c for g, c in eligible)
        overall_grade = weighted_sum / eligible_credits

        G_overall = weighted_sum / total_nonerror_credits
        ungraded_credits = total_nonerror_credits - sum(c for _, c in eligible)
        R_overall = ungraded_credits / total_nonerror_credits if total_nonerror_credits else 0

        if R_overall == 0:
            first_status = "final"
            needed = None
        else:
            raw_needed = (70 - G_overall) / R_overall
            if raw_needed <= 0:
                first_status = "secured"
                needed = 0.0
            elif raw_needed > 100:
                first_status = "impossible"
                needed = round(raw_needed, 1)
            else:
                first_status = "possible"
                needed = round(raw_needed, 1)

        overall = {
            "grade": round(overall_grade, 1),
            "classification": classify(overall_grade),
            "needed_for_first": needed,
            "first_status": first_status,
        }

    return {
        "synced_at": synced_at,
        "overall": overall,
        "excluded_modules": excluded,
        "modules": modules_out,
    }


def load_and_compute(assessments_path: Path, grades_path: Path,
                     assignments_path: Path | None = None) -> dict:
    if not assessments_path.exists():
        return {"error": "assessments.json not found — run setup first"}
    if not grades_path.exists():
        return {"error": "grades.json not found — run: python3 -m bb_sync --grades"}
    assessments = json.loads(assessments_path.read_text())
    grades_raw = json.loads(grades_path.read_text())

    overrides: dict[str, dict] = {}
    if assignments_path and assignments_path.exists():
        for asg in json.loads(assignments_path.read_text()):
            ov = asg.get("status_override")
            if ov:
                mc = asg["module_code"]
                wp = asg["weighting_percent"]
                overrides.setdefault(mc, {})[wp] = ov

    return compute_grades(assessments, grades_raw, overrides=overrides or None)
```

- [ ] **Step 4: Run full backend test suite**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/ -v 2>&1 | tail -40
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard && git add backend/app/services/grades.py backend/tests/test_grades_service.py && git commit -m "feat(backend): derive_status with submitted/upcoming, wire overrides through grades service"
```

---

## Task 6: `grades.py` route — pass `assignments_path`

**Files:**
- Modify: `backend/app/routes/grades.py`

- [ ] **Step 1: Update the route**

Replace the file content:

```python
from fastapi import APIRouter
from app.services.grades import load_and_compute
from app.settings import load_settings

router = APIRouter(prefix="/api/grades", tags=["grades"])


@router.get("")
def get_grades():
    s = load_settings()
    return load_and_compute(s.assessments_path, s.grades_path, s.assignments_path)
```

- [ ] **Step 2: Verify grade route test still passes**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_grades_route.py -v 2>&1 | tail -15
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
cd /home/zozo/University/dashboard && git add backend/app/routes/grades.py && git commit -m "feat(backend): pass assignments_path to load_and_compute for status overrides"
```

---

## Task 7: `types.ts` — update frontend types

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Update `AssessmentGrade.status` and add `status_override` to `Assignment`**

Replace the two relevant type definitions in `types.ts`:

```typescript
export type Assignment = {
  id: string; module_code: string; assignment_title: string; assignment_type: string;
  description: string; deadline_date: string; deadline_time: string;
  weighting_percent: number; word_limit_or_size: string; submission_method: string;
  status: 'upcoming'|'submitted'|'graded';
  status_override?: 'submitted' | null;
  linked_topics: string[]
}
```

```typescript
export type AssessmentGrade = {
  title: string
  weight_percent: number
  score: number | null
  status: 'graded' | 'submitted' | 'upcoming' | 'unmapped'
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/zozo/University/dashboard/frontend && npm run build 2>&1 | tail -20
```

Expected: build may error on `Grades.tsx` (it still uses the old `Assignment` status dropdown) — that's fine, we fix it in Task 8. If there are type errors only in `Grades.tsx`, proceed.

- [ ] **Step 3: Commit**

```bash
cd /home/zozo/University/dashboard && git add frontend/src/lib/types.ts && git commit -m "feat(frontend): add submitted/upcoming to AssessmentGrade.status, add status_override to Assignment"
```

---

## Task 8: `Grades.tsx` + `Grades.module.css` — unified status badge

**Files:**
- Modify: `frontend/src/routes/Grades.tsx`
- Modify: `frontend/src/routes/Grades.module.css`

- [ ] **Step 1: Replace `Grades.tsx` with badge-based UI**

Full replacement:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { GradesResponse, ModuleGrade, OverallGrade } from '../lib/types'
import type { AssessmentGrade } from '../lib/types'
import s from './Grades.module.css'

function clsCls(c: string | null): string {
  if (!c) return ''
  if (c === 'First') return s.first
  if (c === '2:1')   return s.twoOne
  if (c === '2:2')   return s.twoTwo
  if (c === 'Third') return s.third
  return s.fail
}

function OverallCard({ overall, synced_at }: { overall: OverallGrade; synced_at: string | null }) {
  return (
    <div className={s.overallCard}>
      <div className={s.overallLeft}>
        <div className={s.overallGrade}>{overall.grade != null ? `${overall.grade}%` : '—'}</div>
        {overall.classification && (
          <div className={`${s.cls} ${clsCls(overall.classification)}`}>{overall.classification}</div>
        )}
      </div>
      <div className={s.overallRight}>
        <div className={s.overallLbl}>CREDIT-WEIGHTED OVERALL</div>
        {overall.first_status === 'secured' && (
          <div className={s.secured}>First class secured.</div>
        )}
        {overall.first_status === 'possible' && overall.needed_for_first != null && (
          <div className={s.needed}>
            Need <strong>{overall.needed_for_first}%</strong> average across remaining work for a First.
          </div>
        )}
        {overall.first_status === 'impossible' && (
          <div className={s.impossible}>First class no longer possible.</div>
        )}
        {synced_at && (
          <div className={s.sync}>synced {new Date(synced_at).toLocaleString()}</div>
        )}
      </div>
    </div>
  )
}

const STATUS_LABELS: Record<AssessmentGrade['status'], string> = {
  upcoming:  'UPCOMING',
  submitted: 'SUBMITTED',
  graded:    'GRADED',
  unmapped:  '',
}

function ModuleCard({ code, mod }: { code: string; mod: ModuleGrade }) {
  return (
    <div className={s.modCard}>
      <div className={s.modHead}>
        <span className={s.code}>{code}</span>
        <span className={s.modName}>{mod.name}</span>
        <span className={s.credits}>{mod.credits}cr</span>
      </div>

      {mod.error ? (
        <div className={s.errMsg}>{mod.error}</div>
      ) : (
        <>
          <table className={s.table}>
            <tbody>
              {mod.assessments.map(a => (
                <tr key={a.title} className={s.row}>
                  <td className={s.aTitle}>{a.title}</td>
                  <td className={s.aWeight}>{a.weight_percent}%</td>
                  <td className={s.aStatus}>
                    {a.status !== 'unmapped' && (
                      <span className={`${s.statusBadge} ${s[a.status]}`}>
                        {STATUS_LABELS[a.status]}
                      </span>
                    )}
                  </td>
                  <td className={s.aScore}>
                    {a.status === 'graded'   && <span className={s.graded}>{a.score}%</span>}
                    {a.status === 'unmapped' && <span className={s.unmapped}>unmapped</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={s.modFoot}>
            <div>
              <span className={s.lbl}>GRADE SO FAR</span>
              <span className={mod.grade_so_far != null ? clsCls(mod.classification) : ''}>
                {mod.grade_so_far != null ? `${mod.grade_so_far}% (${mod.classification})` : '—'}
              </span>
            </div>
            <div>
              {mod.first_status === 'secured' && <span className={s.secured}>First secured.</span>}
              {mod.first_status === 'possible' && mod.needed_for_first != null && (
                <span className={s.needed}>Need {mod.needed_for_first}% for a First.</span>
              )}
              {mod.first_status === 'impossible' && (
                <span className={s.impossible}>First not possible.</span>
              )}
              {mod.first_status === 'final' && mod.classification && (
                <span>Final: {mod.classification}</span>
              )}
            </div>
            {!mod.weights_ok && <div className={s.warn}>Weights ≠ 100%</div>}
          </div>
        </>
      )}
    </div>
  )
}

export default function Grades() {
  const [data, setData] = useState<GradesResponse | null>(null)
  const [err, setErr]   = useState<string | null>(null)

  useEffect(() => {
    api.grades().then(setData).catch(e => setErr(String(e)))
  }, [])

  if (err)   return <div className={s.err}>{err}</div>
  if (!data) return <div className={s.loading}>Loading grades…</div>
  if (data.error) return (
    <>
      <h1 className={s.h1}>GRADES</h1>
      <div className={s.err}>{data.error}</div>
    </>
  )

  return (
    <>
      <h1 className={s.h1}>GRADES</h1>
      <OverallCard overall={data.overall} synced_at={data.synced_at} />
      {data.excluded_modules.length > 0 && (
        <div className={s.excluded}>Excluded (no access): {data.excluded_modules.join(', ')}</div>
      )}
      <div className={s.grid}>
        {Object.entries(data.modules).map(([code, mod]) => (
          <ModuleCard key={code} code={code} mod={mod} />
        ))}
      </div>
    </>
  )
}
```

- [ ] **Step 2: Replace `Grades.module.css`**

Full replacement:

```css
.h1 { font-family: var(--font-display); font-size: 2.5rem; color: var(--amber); letter-spacing: 0.08em; margin-bottom: 1.5rem; }

/* ── Overall card ────────────────────────────────────────── */
.overallCard  { display: flex; gap: 2rem; align-items: center; background: var(--surface);
                border: 1px solid var(--border); border-left: 4px solid var(--amber);
                padding: 1.5rem 2rem; margin-bottom: 2rem; }
.overallLeft  { flex-shrink: 0; }
.overallGrade { font-family: var(--font-display); font-size: 3.5rem; color: var(--amber);
                line-height: 1; letter-spacing: 0.04em; }
.cls     { font-family: var(--font-mono); font-size: 0.8rem; letter-spacing: 0.15em; margin-top: 0.2rem; }
.overallRight { flex: 1; }
.overallLbl   { font-family: var(--font-mono); font-size: 0.6rem; letter-spacing: 0.25em;
                color: var(--muted); margin-bottom: 0.4rem; }
.sync { font-family: var(--font-mono); font-size: 0.65rem; color: var(--muted); margin-top: 0.5rem; }

/* ── Module grid ─────────────────────────────────────────── */
.grid    { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 1.25rem; }
.modCard { background: var(--surface); border: 1px solid var(--border);
           border-left: 4px solid var(--teal); padding: 1.25rem; }
.modHead { display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 0.85rem; }
.code    { font-family: var(--font-mono); font-size: 0.7rem; color: var(--teal);
           border: 1px solid color-mix(in srgb, var(--teal) 50%, transparent); padding: 0.15rem 0.4rem;
           flex-shrink: 0; }
.modName { font-size: 0.88rem; color: var(--text); flex: 1; }
.credits { font-family: var(--font-mono); font-size: 0.65rem; color: var(--muted); flex-shrink: 0; }

/* ── Assessment table ────────────────────────────────────── */
.table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; }
.row   { border-bottom: 1px solid var(--border); }
.row:last-child { border-bottom: none; }
.aTitle  { padding: 0.4rem 0; font-size: 0.82rem; color: var(--text-2); }
.aWeight { padding: 0.4rem 0.5rem; font-family: var(--font-mono); font-size: 0.7rem;
           color: var(--muted); white-space: nowrap; width: 3rem; text-align: right; }
.aStatus { padding: 0.4rem 0.5rem; white-space: nowrap; width: 7rem; }
.aScore  { padding: 0.4rem 0; text-align: right; white-space: nowrap; width: 5.5rem; }

/* Status badges */
.statusBadge { font-family: var(--font-mono); font-size: 0.6rem; letter-spacing: 0.1em; }
.statusBadge.upcoming  { color: var(--muted); }
.statusBadge.submitted { color: var(--teal); }
.statusBadge.graded    { color: var(--amber); }

/* Score badges */
.graded   { font-family: var(--font-mono); font-size: 0.82rem; color: var(--amber); }
.unmapped { font-family: var(--font-mono); font-size: 0.62rem; letter-spacing: 0.1em;
            color: var(--muted); border: 1px dashed var(--border); padding: 0.1rem 0.3rem; }

/* ── Module footer ───────────────────────────────────────── */
.modFoot { display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap;
           border-top: 1px dashed var(--border); padding-top: 0.65rem;
           font-family: var(--font-mono); font-size: 0.72rem; }
.modFoot > div { display: flex; flex-direction: column; gap: 0.15rem; }
.lbl { font-size: 0.58rem; letter-spacing: 0.2em; color: var(--muted); }

/* ── Classification colours ──────────────────────────────── */
.first  { color: var(--amber); }
.twoOne { color: var(--teal); }
.twoTwo { color: var(--purple); }
.third  { color: var(--text-2); }
.fail   { color: var(--maroon); }

/* ── First status ────────────────────────────────────────── */
.secured    { color: var(--teal); }
.needed     { color: var(--text-2); }
.impossible { color: var(--maroon); }
.warn { font-family: var(--font-mono); font-size: 0.62rem; color: var(--maroon); }

/* ── Misc ────────────────────────────────────────────────── */
.errMsg   { color: var(--maroon); font-size: 0.85rem; }
.excluded { font-family: var(--font-mono); font-size: 0.7rem; color: var(--muted); margin-bottom: 1rem; }
.err      { color: var(--maroon); font-size: 0.85rem; margin-top: 2rem; }
.loading  { color: var(--muted); font-size: 0.85rem; margin-top: 2rem; }
```

- [ ] **Step 3: Run TypeScript build to catch type errors**

```bash
cd /home/zozo/University/dashboard/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors

- [ ] **Step 4: Run frontend tests**

```bash
cd /home/zozo/University/dashboard/frontend && npm test 2>&1 | tail -20
```

Expected: all PASS

- [ ] **Step 5: Check Grades page in browser**

The dev server should already be running on port 5173. Open it:

```bash
export PATH="$HOME/.local/bin:$PATH"
BU_CDP_URL=http://127.0.0.1:9222 browser-harness -c '
new_tab("http://localhost:5173/grades")
wait_for_load()
import time; time.sleep(2)
capture_screenshot("/tmp/grades_after.png")
'
```

Verify:
- No dropdown selects visible
- Each assessment row shows a status badge (UPCOMING / SUBMITTED / GRADED)
- Graded assessments show a score in the right column
- GRADED badge is amber, SUBMITTED is teal, UPCOMING is muted

- [ ] **Step 6: Commit**

```bash
cd /home/zozo/University/dashboard && git add frontend/src/routes/Grades.tsx frontend/src/routes/Grades.module.css && git commit -m "feat(frontend): replace status dropdown with unified badge on Grades page"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| BB `get_column_grade` returns `bb_status` | Task 1 |
| `grades.json` columns include `bb_status` | Task 2 |
| `assignments.json` gets optional `status_override` field | Task 7 (type), referenced in Task 5 `load_and_compute` |
| `derive_status` priority: score → NeedsGrading → override → upcoming | Task 5 |
| `AssessmentGrade.status` gains "submitted" | Tasks 5 + 7 |
| Auto-promote `assignments.json` after sync | Tasks 3 + 4 |
| `find_column` prefers submitted column over upcoming | Task 5 |
| Frontend: dropdown removed, badge shown | Task 8 |
| SUBMITTED badge = amber, UPCOMING = muted | Task 8 |
| Grade math unchanged (submitted treated as ungraded) | Task 5 (submitted goes to `ungraded_weight`) |

**Placeholder scan:** None found. All steps include exact code.

**Type consistency check:**
- `derive_status` defined in Task 5, used in Task 5 only ✓
- `AssessmentGrade.status` updated in Task 7 types, consumed in Task 8 JSX via `s[a.status]` and `STATUS_LABELS[a.status]` ✓
- `_derive_status` in syncer (Task 4) and `derive_status` in backend (Task 5) are separate functions in separate packages — intentionally no shared code ✓
- `overrides: dict | None` passed from `compute_grades` → `compute_module` in Task 5 ✓
- `assignments_path: Path | None = None` added to both `GradeSyncer` (Task 4) and `load_and_compute` (Task 5) ✓
