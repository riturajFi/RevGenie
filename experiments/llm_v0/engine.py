from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.llm_v0.api import ExperimentApi
from experiments.llm_v0.store import THIS_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone v0 LLM loops")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")
    subparsers.add_parser("state")

    loop1_parser = subparsers.add_parser("loop1")
    loop1_parser.add_argument(
        "--scenarios",
        default=str(THIS_DIR / "sample" / "scenarios.json"),
    )

    loop2_parser = subparsers.add_parser("loop2")
    loop2_parser.add_argument(
        "--audits",
        default=str(THIS_DIR / "sample" / "audits.json"),
    )

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--source", required=True)
    log_parser.add_argument("--message", required=True)
    log_parser.add_argument("--metadata", default="{}")

    revert_parser = subparsers.add_parser("revert")
    revert_parser.add_argument("kind", choices=["prompt", "evaluator"])
    revert_parser.add_argument("--version-id")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    api = ExperimentApi()

    if args.command == "init":
        print(json.dumps(api.init_experiment().model_dump(), indent=2))
        return

    if args.command == "state":
        print(json.dumps(api.get_state().model_dump(), indent=2))
        return

    if args.command == "loop1":
        print(json.dumps(api.run_loop1(args.scenarios).model_dump(), indent=2))
        return

    if args.command == "loop2":
        print(json.dumps(api.run_loop2(args.audits).model_dump(), indent=2))
        return

    if args.command == "log":
        metadata = json.loads(args.metadata)
        print(json.dumps(api.collect_log(args.source, args.message, metadata=metadata).model_dump(), indent=2))
        return

    if args.kind == "prompt":
        version = api.revert_loop1(args.version_id)
    else:
        version = api.revert_loop2(args.version_id)
    print(json.dumps(version.model_dump(), indent=2))


if __name__ == "__main__":
    main()
