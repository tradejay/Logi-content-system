"""Submit one completed implementation to the persistent review queue."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.review_app.auto_reviewer import enqueue_auto_review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task_id')
    parser.add_argument('--base')
    parser.add_argument('--context', help='Task-specific source/evidence manifest relative to project root')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}', args.task_id):
        parser.error('Invalid task ID')
    job, created = enqueue_auto_review(args.task_id, base_ref=args.base, context_file=args.context)
    print(f"{job['job_id']}: {'queued' if created else 'already registered'}")


if __name__ == '__main__':
    main()
