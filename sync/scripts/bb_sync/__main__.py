import sys
import json
import argparse
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from config import (BB_BASE_URL, LOCAL_ROOT, SYNC_MODULES, local_path_for_course, module_code,
                    current_term_codes, ASSESSMENTS_PATH, GRADES_PATH, ASSIGNMENTS_PATH)
from bb_session import BbSession
from bb_client import BlackboardClient
from syncer import Syncer
from grades import GradeSyncer

# Exit code the dashboard maps to "Connect Blackboard".
EXIT_NOT_LOGGED_IN = 3


def _print_grade_result(result: dict, file=sys.stdout) -> None:
    for code, data in result.items():
        if code == "synced_at":
            continue
        if "error" in data:
            print(f"  {code}: {data['error']}", file=file)
        else:
            graded = sum(1 for c in data.get("columns", []) if c["status"] == "graded")
            print(f"  {code}: {graded}/{len(data.get('columns', []))} columns graded", file=file)


def _login() -> None:
    """Open a visible browser window and wait for the user to log in to Blackboard."""
    print("Opening a browser window — log in to Blackboard there.", file=sys.stderr, flush=True)
    try:
        with BbSession(headless=False) as bb:
            me = bb.interactive_login()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    if not me:
        print("ERROR: Login not completed (window closed or timed out).", file=sys.stderr)
        sys.exit(EXIT_NOT_LOGGED_IN)
    print(json.dumps({"user": me.get("userName") or me.get("id")}))
    sys.exit(0)


def _run_grades(client, user_id, modules, courses, out) -> None:
    assessments_path = Path(ASSESSMENTS_PATH)
    if not assessments_path.exists():
        print(f"Skipping grades: no assessments.json at {assessments_path}", file=out)
        return
    print("\nRunning grade sync…", file=out)
    grades_path = Path(GRADES_PATH)
    grade_syncer = GradeSyncer(client, assessments_path, grades_path,
                               assignments_path=Path(ASSIGNMENTS_PATH))
    result = grade_syncer.sync(user_id, modules=modules, courses=courses)
    _print_grade_result(result, file=out)
    print(f"Grades written to {grades_path}", file=out)


def main():
    parser = argparse.ArgumentParser(description="Blackboard file + grade sync")
    parser.add_argument("--login", action="store_true",
                        help="Open a browser window to log in to Blackboard, then exit")
    parser.add_argument("--list-courses", action="store_true",
                        help="Output enrolled courses as JSON and exit")
    parser.add_argument("--grades", action="store_true",
                        help="Sync grades only (skip file content-tree walk)")
    parser.add_argument("--no-grades", action="store_true",
                        help="Sync files only (skip grade sync)")
    parser.add_argument("--modules", nargs="+", metavar="CODE",
                        help="Module codes to sync (default: BB_SYNC_MODULES, else current term)")
    args = parser.parse_args()

    if args.login:
        _login()

    # In --list-courses mode all status goes to stderr so stdout stays clean JSON
    out = sys.stderr if args.list_courses else sys.stdout
    print(f"Blackboard Sync — {BB_BASE_URL}", file=out, flush=True)

    try:
        bb = BbSession(headless=True)
        bb.open()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=out)
        sys.exit(1)

    with bb:
        print("Checking Blackboard session…", file=out, flush=True)
        me = bb.ensure_logged_in()
        if not me:
            print("ERROR: Not connected to Blackboard — click 'Connect Blackboard' on the Sync page "
                  "(or run: python -m bb_sync --login).", file=out)
            sys.exit(EXIT_NOT_LOGGED_IN)
        user_id = me.get("id")
        if not user_id:
            print("ERROR: Could not retrieve user ID from Blackboard response.", file=out)
            sys.exit(1)
        print(f"Logged in as: {me.get('userName', user_id)}", file=out)

        client = BlackboardClient(bb)
        print("Fetching enrolled courses…", file=out, flush=True)
        courses = client.get_courses(user_id)

        if args.list_courses:
            print(json.dumps([
                {"id": c["id"], "name": c.get("name") or "",
                 "code": module_code(c.get("name") or ""), "term_id": c.get("term_id", ""),
                 "available": c.get("available", True)}
                for c in courses
            ]))
            sys.exit(0)

        if not courses:
            print("No active courses found.", file=out)
            sys.exit(0)

        if args.modules:
            selected = {m.upper() for m in args.modules}
        elif SYNC_MODULES:
            selected = SYNC_MODULES
        else:
            selected = current_term_codes(courses)

        if args.grades:
            _run_grades(client, user_id, sorted(selected) if args.modules else None, courses, out)
            sys.exit(0)

        syncer = Syncer(client, LOCAL_ROOT)
        print(f"Found {len(courses)} active course(s):", flush=True)
        synced_codes = []
        for c in courses:
            course_name = c.get("name", "")
            if not course_name:
                print(f"  [skip] Course {c.get('id', '?')} has no name, skipping")
                continue
            code = module_code(course_name)
            if code not in selected:
                print(f"  [skip] {course_name!r} not in selected modules")
                continue

            if not c.get("available", True):
                print(f"  [not published yet] {course_name} — the lecturer hasn't opened it to students")
                continue

            folder_name = local_path_for_course(course_name)
            local_path = str(Path(LOCAL_ROOT) / folder_name)
            print(f"  {course_name} → {local_path}", flush=True)
            try:
                syncer.sync_course(c["id"], course_name, local_path)
                synced_codes.append(code)
            except Exception as e:
                print(f"  [error] Failed to sync {course_name}: {e}")

        print("\nSync complete.", flush=True)
        if synced_codes:
            print(f"__synced__:{','.join(synced_codes)}")

        if not args.no_grades:
            _run_grades(client, user_id, synced_codes, courses, out)


if __name__ == "__main__":
    main()
