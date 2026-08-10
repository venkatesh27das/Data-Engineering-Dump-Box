import argparse

from app.config import get_settings
from app.services.demo_reset import (
    DemoResetSafetyError,
    build_reset_plan,
    count_neo4j_project_nodes,
    reset_local_demo,
    reset_neo4j_project,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or reset Knowledge Graph Builder demo state.")
    parser.add_argument("--yes", action="store_true", help="Apply the reset without an interactive confirmation.")
    parser.add_argument("--neo4j-project-id", help="Also remove KnowledgeAsset nodes for exactly this project id from Neo4j.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        plan = build_reset_plan(settings)
        print("Local reset preview")
        for table, count in plan.table_counts.items():
            print(f"  {table}: {count} records")
        print(f"  managed files: {len(plan.files)}")
        for path in plan.files:
            print(f"    {path}")

        neo4j_count = 0
        if args.neo4j_project_id:
            neo4j_count = count_neo4j_project_nodes(settings, args.neo4j_project_id)
            print(f"Neo4j project {args.neo4j_project_id}: {neo4j_count} KnowledgeAsset nodes")

        if not args.yes:
            confirmation = input("Type reset-demo to apply this reset: ").strip()
            if confirmation != "reset-demo":
                print("Reset cancelled; nothing changed.")
                return 1

        applied = reset_local_demo(settings)
        deleted_neo4j = reset_neo4j_project(settings, args.neo4j_project_id) if args.neo4j_project_id else 0
        print(f"Reset complete: {applied.record_count} local records and {len(applied.files)} managed files removed.")
        if args.neo4j_project_id:
            print(f"Neo4j cleanup complete: {deleted_neo4j} project-scoped nodes removed.")
        print("Reload the app; stale project and run identifiers will be cleared automatically.")
        return 0
    except (DemoResetSafetyError, OSError) as error:
        print(f"Reset refused: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
