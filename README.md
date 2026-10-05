# University Dashboard

Local study hub for your Blackboard modules: synced course files, grades, deadlines, tasks, notes and topic confidence. Everything runs on your own machine at **http://localhost:8765**.

## Quick Start

**Step 1 — install [uv](https://docs.astral.sh/uv/) (one-time, ~30 seconds)**

```bash
# Mac / Linux / WSL2
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 2 — clone**

```bash
git clone https://github.com/zshahzada1/university-dashboard.git
cd university-dashboard
```

**Step 3 — run**

```bash
uv run start.py        # Mac / Linux / WSL2
run.bat                # Windows (double-click or terminal)
```

uv installs Python and every dependency on first run. The server starts at **http://localhost:8765**.

**Step 4 — connect Blackboard (first time only)**

Open the **Sync** page and click **Connect Blackboard**. A browser window opens on the university login. Sign in as usual, SSO and MFA included. The window closes itself once you're in, and your modules appear.

## Connecting to Blackboard

The dashboard drives Blackboard through its **own browser profile** (`~/.uni-dashboard/bb-profile`), separate from your everyday browsing profile:

- **One-time login.** You sign in once in a visible window. Later syncs reuse the saved session headlessly, in the background.
- **Silent renewal.** When Blackboard's session lapses, the dashboard first tries a silent round-trip through the university's Microsoft sign-in. You only see **Not connected** if that fails; click **Connect Blackboard** to log in again.
- **Browser choice.** It uses **Brave** if installed, otherwise Microsoft Edge, then Google Chrome, then a bundled Chromium (downloaded once if none of those exist). To force a browser, set `BB_BROWSER_PATH` to its executable.
- **Password never seen.** The app never sees or stores your password. Login happens entirely on the university's own pages.

> **Why not use my normal browser session?** Chromium-based browsers (Chrome, Edge, Brave) refuse remote control of your everyday profile since v136. That protection exists because malware abused it to steal logins. Reading cookies out of the browser's files means defeating its encryption, which is how infostealers behave. A dedicated profile gives you the same one-time login without either risk.

## Syncing

On the **Sync** page:

1. Pick modules. **This year** selects the current term: the term with the most modules, ties going to the latest academic year.
2. Choose **Files + Grades**, **Files only** or **Grades only**.
3. Click **Sync**. Progress streams live.

What a sync does:

- **Files** are mirrored into `~/University/<MODULE>/`, following Blackboard's folder structure. Included:
  - attachments;
  - files embedded in pages, including ones displayed inside the page;
  - page bodies, saved as `.html`;
  - documents that pages link to on Blackboard or the university's SharePoint (fetched with your Microsoft sign-in).

  A SharePoint link whose file has been moved to a different format (e.g. `.docx` → `.pdf`) is followed to the new file. A dead link is reported as `[broken link]`. Documents on other websites are listed in the log but not downloaded.
- **Re-running is cheap.** Unchanged files are skipped. Files a lecturer replaces on Blackboard are downloaded again, tracked by a hidden `.bbsync-manifest.json` per module.
- **Unpublished courses** (not yet opened to students) are reported as *not published yet*. They sync automatically once the lecturer publishes them.
- **New modules** are added to the dashboard (name, colour, topics) after their first sync.
- **Robust to errors.** One failing file, for example one open in Word, is logged and skipped. It never aborts the module.

From a terminal (run from `sync/scripts`):

```bash
uv run --with requests --with playwright python -m bb_sync --login                  # login window
uv run --with requests --with playwright python -m bb_sync                          # this term: files + grades
uv run --with requests --with playwright python -m bb_sync --modules FN668 FN678    # chosen modules
uv run --with requests --with playwright python -m bb_sync --grades                 # grades only
```

See [`sync/README.md`](sync/README.md) for every flag and setting.

### Grades setup

Grade sync needs `backend/data/assessments.json`, which describes each module's assessments and weightings. Each `column_name` must match (as a substring) the Blackboard gradebook column. `course_id` is optional; it's found from your enrolments.

```json
{
  "FN668": {
    "name": "Finance and Risk Management",
    "credits": 20,
    "assessments": [
      {"title": "Coursework", "weight_percent": 50, "column_name": "Coursework"},
      {"title": "Exam",       "weight_percent": 50, "column_name": "Exam"}
    ]
  }
}
```

The **Grades** page then shows weighted averages, the degree classification so far, and the mark needed for a First. Assignment statuses (upcoming / submitted / graded) are updated from the gradebook automatically.

## Features

| Section | Description |
|---|---|
| Home | Today's tasks, next deadline and countdowns to upcoming assessments |
| Planner | Quick task capture, week view of tasks / assessments / events, and study suggestions for low-confidence topics |
| Modules | Per-module topics with confidence ratings, topic files and markdown notes |
| Grades | Module breakdowns, weighted averages, classification and projections |
| Files | Tree browser for all synced Blackboard content; PDFs open in the browser, Office files in their desktop app |
| Sync | Blackboard connection, module picker and live sync log |

The API also offers file-name search across module folders (`GET /api/search?q=…`), which has no UI yet.

## Security & privacy

- **Local-only server.** The server listens on `127.0.0.1` only. It rejects requests addressed to other host names (DNS-rebinding protection) and refuses state-changing requests from other websites (CSRF protection).
- **Scoped cookies.** Blackboard cookies are only ever sent to the hosts they belong to. Links to third-party sites inside course pages never receive them.
- **Personal data stays out of git.** Your data (`backend/data/`: modules, tasks, notes, grades) is gitignored and never leaves your machine.
- **Reset the login.** To forget the Blackboard login, delete `~/.uni-dashboard/bb-profile`.

## Architecture

```
university-dashboard/
  start.py      — uv entry point (PEP 723 inline script)
  run.sh        — Mac / Linux / WSL2 launcher (also: ./run.sh dev)
  run.bat       — Windows launcher
  backend/      — FastAPI app, port 8765; JSON storage in backend/data/
  frontend/     — React + TypeScript + Vite (pre-built dist/ committed)
  sync/         — bb_sync: Playwright Blackboard session, file + grade sync
```

The backend runs `bb_sync` as a subprocess for login, course listing and sync, one at a time, since the browser profile can only be open once. Output streams to the Sync page over server-sent events.

## Development

```bash
./run.sh dev          # hot reload — frontend http://localhost:5173, backend http://localhost:8765
```

Tests:

```bash
cd backend && uv run --extra dev pytest
cd sync/scripts/bb_sync && uv run --no-project --with requests --with playwright --with pytest python -m pytest
cd frontend && npm ci && npm test
```

After frontend changes, run `npm run build` in `frontend/` and commit `frontend/dist/`, so users without Node get the update.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `UNI_DIR` | `~/University` | Root folder for synced module files |
| `UNI_DATA_DIR` | `backend/data/` | JSON data directory |
| `UNI_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Host names the server answers to |
| `BBSYNC_PYTHON` | current interpreter | Python used for the bb_sync subprocess |
| `BBSYNC_SCRIPTS_DIR` | `sync/scripts/` | Working directory for bb_sync |
| `BB_BASE_URL` | `https://studentcentral.brighton.ac.uk` | Blackboard instance URL |
| `BB_PROFILE_DIR` | `~/.uni-dashboard/bb-profile` | Browser profile holding the Blackboard login |
| `BB_BROWSER_PATH` | Brave if installed | Chromium-based browser executable to use |
| `BB_SYNC_MODULES` | *(current term)* | Comma-separated default modules for CLI syncs |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Sync page says **Not connected** | Click **Connect Blackboard** and sign in |
| A module syncs no files and shows *not published yet* | The lecturer hasn't opened the course to students; sync again later |
| **Blackboard is busy** | A login or sync is already running; wait for it to finish |
| Login window keeps reappearing | Delete `~/.uni-dashboard/bb-profile`, restart, connect again |
| Grades page says `assessments.json not found` | Create it (see [Grades setup](#grades-setup)) |
