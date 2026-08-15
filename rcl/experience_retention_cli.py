from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experience_retention import (
    create_experience_archive_record,
    evaluate_experience_retention,
    load_default_experience_retention_policy,
)


def _read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(value, *, output: str | None, as_json: bool) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)
    elif as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def _evaluate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl evaluate-experience-retention")
    parser.add_argument("store")
    parser.add_argument("summary")
    parser.add_argument("--policy")
    parser.add_argument("--archive-record", action="append", default=[])
    parser.add_argument("--as-of")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run_evaluate(argv: list[str]) -> int:
    args = _evaluate_parser().parse_args(argv)
    store = _read_json(args.store)
    summary = _read_json(args.summary)
    policy = _read_json(args.policy) if args.policy else load_default_experience_retention_policy()
    archive_records = [_read_json(path) for path in args.archive_record]
    report = evaluate_experience_retention(
        store,
        summary,
        policy=policy,
        archive_records=archive_records,
        as_of=args.as_of,
    )

    if args.output or args.json:
        _emit(report, output=args.output, as_json=args.json)
        return 0

    print("RCL Experience Retention Review")
    print(f"Store: {report['source']['store_id']}")
    print(f"Summary: {report['summary']['summary_id']}")
    print("Summary Binding: VERIFIED")
    print(f"As Of: {report['as_of']}")
    print(
        "Decisions: "
        f"retain={report['counts']['retain']} "
        f"archive_candidate={report['counts']['archive_candidate']} "
        f"prune_candidate={report['counts']['prune_candidate']}"
    )
    for item in report["decisions"]:
        print(
            f"- {item['episode_id']}: {item['decision'].upper()} "
            f"age={item['age_days']}d group={item['group_episode_count']} "
            f"archived={'YES' if item['archived'] else 'NO'} "
            f"reasons={','.join(item['reasons'])}"
        )
    print("Source Mutation: NO")
    print("Prune Executed: NO")
    print("Archive Executed By RCL: NO")
    return 0


def _archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcl record-experience-archive")
    parser.add_argument("store")
    parser.add_argument("--episode-id", action="append", required=True)
    parser.add_argument("--location-ref", required=True)
    parser.add_argument("--archived-at", required=True)
    parser.add_argument("--archived-by", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    return parser


def run_archive(argv: list[str]) -> int:
    args = _archive_parser().parse_args(argv)
    record = create_experience_archive_record(
        _read_json(args.store),
        args.episode_id,
        location_ref=args.location_ref,
        archived_at=args.archived_at,
        archived_by=args.archived_by,
    )

    if args.output or args.json:
        _emit(record, output=args.output, as_json=args.json)
        return 0

    print("RCL Experience Archive Record")
    print(f"Archive ID: {record['archive_id']}")
    print(f"Store: {record['source']['store_id']}")
    print(f"Episodes: {record['episode_count']}")
    print(f"Location Ref: {record['location_ref']}")
    print("Archive Assertion: DEPLOYMENT-ASSERTED EXTERNAL COPY")
    print("Archive Executed By RCL: NO")
    print("Source Mutation: NO")
    return 0
