# Uni Hub — Frontend

React + TypeScript + Vite frontend for the Uni Hub dashboard.

## Dev server

```bash
npm run dev
# http://localhost:5173
```

API calls proxy to the FastAPI backend at `http://localhost:8765`. Start the backend first (or use `./run.sh dev` from the repo root to start both).

## Build

```bash
npm run build
# output: dist/
```

The backend serves `dist/` at `/` in production — no separate web server needed.

## Pages

| Route | Description |
|---|---|
| `/` | Overview / home |
| `/grades` | Grade breakdown by module with weighted averages |
| `/files` | File tree browser for synced Blackboard content |
| `/assignments` | Deadline tracker |
| `/tasks` | Personal task list |
| `/events` | Upcoming events |
| `/notes` | Per-module markdown notes |
| `/topics` | Topic confidence tracker |
| `/search` | Full-text search |
| `/sync` | Blackboard sync trigger with live output stream |

## Stack

- React 18 + TypeScript
- Vite (dev server + bundler)
- ESLint + TypeScript ESLint

## Tests

```bash
npm test
```
