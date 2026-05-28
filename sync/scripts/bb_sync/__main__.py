import sys
import json
import argparse
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from config import BB_BASE_URL, LOCAL_ROOT, local_path_for_course, should_sync_course, MODULE_CODE_RE, ASSESSMENTS_PATH, GRADES_PATH, ASSIGNMENTS_PATH
from cdp_client import CdpSession
from bb_client import BlackboardClient
from syncer import Syncer
from grades import GradeSyncer


def _print_grade_result(result: dict, file=sys.stdout) -> None:
    for code, data in result.items():
        if code == "synced_at":
            continue
        if "error" in data:
            print(f"  {code}: {data['error']}", file=file)
        else:
            graded = sum(1 for c in data.get("columns", []) if c["status"] == "graded")
            print(f"  {code}: {graded}/{len(data.get('columns', []))} columns graded", file=file)


def main():
    parser = argparse.ArgumentParser(description="Blackboard file sync")
    parser.add_argument("--refresh-cookies", action="store_true",
                        help="(no-op) Kept for CLI compatibility")
    parser.add_argument("--list-courses", action="store_true",
                        help="Output enrolled courses as JSON and exit")
    parser.add_argument("--grades", action="store_true",
                        help="Sync grades only (skip file content-tree walk)")
    parser.add_argument("--modules", nargs="+", metavar="CODE",
                        help="Module codes to sync (overrides config allowlist)")
    args = parser.parse_args()

    # In --list-courses mode all status goes to stderr so stdout stays clean JSON
    out = sys.stderr if args.list_courses else sys.stdout

    print(f"Blackboard Sync — {BB_BASE_URL}", file=out)

    print("Connecting to Blackboard tab in Edge…", file=out)
    try:
        cdp = CdpSession()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=out)
        sys.exit(1)

    with cdp:
        client = BlackboardClient(cdp)
        syncer = Syncer(client, LOCAL_ROOT)

        print("Checking authentication…", file=out)
        try:
            me = client.get_current_user()
        except Exception as e:
            print(f"ERROR: Could not authenticate with Blackboard: {e}", file=out)
            print("Make sure Edge has a Blackboard tab open and you are logged in.", file=out)
            sys.exit(1)

        user_id = me.get("id")
        if not user_id:
            print("ERROR: Could not retrieve user ID from Blackboard response.", file=out)
            sys.exit(1)
        print(f"Logged in as: {me.get('userName', user_id)}", file=out)

        print("Fetching enrolled courses…", file=out)
        courses = client.get_courses(user_id)
        if not courses:
            print("No active courses found.", file=out)
            if args.list_courses:
                print(json.dumps([]))
            sys.exit(0)

        if args.list_courses:
            result = []
            for c in courses:
                name = c.get("name", "") or ""
                match = MODULE_CODE_RE.search(name) if name else None
                result.append({
                    "id": c["id"],
                    "name": name,
                    "code": match.group(1) if match else None,
                    "term_id": c.get("term_id", ""),
                })
            print(json.dumps(result))
            sys.exit(0)

        if args.grades:
            print("Running grade sync…", file=out)
            assessments_path = Path(ASSESSMENTS_PATH)
            if not assessments_path.exists():
                print(f"ERROR: assessments.json not found at {assessments_path}", file=out)
                print("Create it from the briefs before running --grades.", file=out)
                sys.exit(1)
            grades_path = Path(GRADES_PATH)
            grade_syncer = GradeSyncer(client, assessments_path, grades_path,
                                       assignments_path=Path(ASSIGNMENTS_PATH))
            result = grade_syncer.sync(user_id, modules=args.modules)
            _print_grade_result(result, file=out)
            print(f"\nGrades written to {grades_path}", file=out)
            sys.exit(0)

        modules_filter = set(args.modules) if args.modules else None

        print(f"Found {len(courses)} active course(s):")
        for c in courses:
            course_name = c.get("name", "")
            if not course_name:
                print(f"  [skip] Course {c.get('id', '?')} has no name, skipping")
                continue

            if modules_filter is not None:
                m = MODULE_CODE_RE.search(course_name)
                if not m or m.group(1) not in modules_filter:
                    print(f"  [skip] {course_name!r} not in selected modules")
                    continue
            elif not should_sync_course(course_name):
                print(f"  [skip] {course_name!r} not in module allowlist")
                continue

            folder_name = local_path_for_course(course_name)
            if not folder_name:
                print(f"  [skip] Could not determine local folder for: {course_name!r}")
                continue
            local_path = str(Path(LOCAL_ROOT) / folder_name)
            print(f"  {course_name} → {local_path}")
            try:
                syncer.sync_course(c["id"], course_name, local_path)
            except Exception as e:
                print(f"  [error] Failed to sync {course_name}: {e}")

        print("\nSync complete.")

        assessments_path = Path(ASSESSMENTS_PATH)
        if assessments_path.exists():
            print("\nRunning grade sync…")
            grades_path = Path(GRADES_PATH)
            grade_syncer = GradeSyncer(client, assessments_path, grades_path,
                                       assignments_path=Path(ASSIGNMENTS_PATH))
            result = grade_syncer.sync(user_id, modules=None)
            _print_grade_result(result)
            print(f"Grades written to {grades_path}")


if __name__ == "__main__":
    main()
