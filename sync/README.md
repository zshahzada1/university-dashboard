# bb_sync

Syncs files and grades from Blackboard Ultra into `~/University/<MODULE>/`. It's invoked by the dashboard's Sync page and can also be run from the terminal.

## How it works

1. **Login.** Blackboard is driven through a dedicated [Playwright](https://playwright.dev/python/) browser profile (`~/.uni-dashboard/bb-profile`). You log in once in a visible window (`--login`); the session is saved and later runs are headless. When Blackboard's session lapses, a silent SSO round-trip is tried before asking you to log in again. Login is detected by calling `users/me`, both from inside the page and directly with the browser's cookie jar.
2. **Browser.** Browsers are tried in this order:
   - `BB_BROWSER_PATH`
   - Brave (if installed)
   - Edge
   - Chrome
   - Playwright's bundled Chromium, installed once on demand.
3. **API calls.** Blackboard REST calls run as `fetch()` inside a Blackboard page, so the browser supplies the session headers Blackboard expects.
4. **Course selection.** With no `--modules`, the current term is synced: the term with the most coded courses, with ties going to the latest year in the course titles. Courses the lecturer hasn't published yet are reported as `[not published yet]` and skipped.
5. **Content walk.** The content tree of each selected module is walked. Attachments are streamed to a `.tmp` file and renamed on completion; document bodies are saved as `.html`.
   - **Embedded files.** Files embedded in a page body (`data-bbfile`) are downloaded, whether Blackboard shows them as a link (`render: inline`) or displays them inside the page (`render: inlineOnly`). Only images marked `isDecorative` are skipped.
   - **Linked documents.** Plain links whose path ends in a document extension (`.pdf`, `.docx`, `.pptx`, `.xlsx`, …) are followed:
     - On Blackboard, they're streamed like attachments.
     - On `*.sharepoint.com`, they're fetched through the browser profile's Microsoft sign-in. A dead `.docx`/`.pdf` link falls back to the same name with the other extension, and anything still missing is logged as `[broken link]`.
     - On other sites, they're logged as `[link]` and not downloaded.
6. **Updates.** A per-module `.bbsync-manifest.json` records each item's Blackboard `modified` time, so files the lecturer replaces are downloaded again. Unchanged files are skipped, so it's safe to re-run at any time.
7. **Grades.** Grades are synced for modules listed in `backend/data/assessments.json` and written to `backend/data/grades.json`.

Downloads use a cookie jar scoped to the cookies' own domains, so session cookies are never sent to third-party links embedded in course pages.

## Usage

Run from `sync/scripts` (the dashboard does this for you):

```bash
python -m bb_sync --login                      # open a window and log in (first time / after expiry)
python -m bb_sync                              # current term's modules: files + grades
python -m bb_sync --modules BY138 BY150        # specific modules: files + grades
python -m bb_sync --modules BY138 --no-grades  # files only
python -m bb_sync --grades                     # grades only
python -m bb_sync --list-courses               # enrolled courses as JSON
```

Exit code `3` means "not logged in" (the dashboard shows **Connect Blackboard**).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BB_BASE_URL` | `https://studentcentral.brighton.ac.uk` | Blackboard instance URL |
| `BB_LOCAL_ROOT` | `~/University` | Root folder where module folders are created |
| `BB_PROFILE_DIR` | `~/.uni-dashboard/bb-profile` | Dedicated browser profile + saved session |
| `BB_BROWSER_PATH` | *(Brave if installed)* | Chromium-based browser executable to drive |
| `BB_SYNC_MODULES` | *(empty = current term)* | Comma-separated default module allowlist |
| `BB_ASSESSMENTS_PATH` | `backend/data/assessments.json` | Assessment config for grade sync |
| `BB_GRADES_PATH` | `backend/data/grades.json` | Grade sync output |
| `BB_ASSIGNMENTS_PATH` | `backend/data/assignments.json` | Assignment statuses promoted from grades |

When launched from the dashboard, the backend passes its own folders through these variables.

`assessments.json` maps module codes to their assessments. `course_id` is optional; it's looked up from your enrolments when omitted:

```json
{
  "BY138": {
    "name": "Economics", "credits": 20,
    "assessments": [{"title": "Essay", "weight_percent": 50, "column_name": "Essay"}]
  }
}
```

## File layout

```
sync/
  sync.sh              — shell wrapper (uses scripts/.venv if present)
  requirements.txt     — requests, playwright, pytest
  scripts/bb_sync/
    __main__.py        — CLI entry point
    bb_session.py      — Playwright browser session: login, in-page fetch, cookie jar
    bb_client.py       — Blackboard REST API client
    config.py          — URLs, paths, module selection
    syncer.py          — content tree walker + manifest-aware downloader
    grades.py          — GradeSyncer: grade columns + assignment status promotion
    test_*.py          — unit tests
```

## Running tests

```bash
cd sync/scripts/bb_sync
uv run --no-project --with requests --with playwright --with pytest python -m pytest
```

## Troubleshooting

- **"Not connected to Blackboard."** Click **Connect Blackboard** on the Sync page, or run `python -m bb_sync --login`.
- **"Blackboard is busy."** Only one login/sync can use the browser profile at a time. Wait for the current one to finish.
- **A module shows `[not published yet]`.** The course exists, but students can't open it yet; Blackboard returns 403. It will sync once it's published.
- **Stuck login state.** Delete `~/.uni-dashboard/bb-profile` and connect again.
