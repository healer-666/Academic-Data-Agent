"""Maintainer CLI for producing reviewed competition case cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.case_pipeline import (  # noqa: E402
    CasePipeline,
    CasePipelineError,
    ConfiguredCaseExtractor,
    JsonFileCaseExtractor,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and review curated competition case cards.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("generate", "regenerate"):
        generate = subparsers.add_parser(command, help=f"{command.title()} an immutable draft revision.")
        generate.add_argument("--manifest", required=True, help="Path to the maintainer YAML manifest.")
        generate.add_argument("--workspace", required=True, help="Private maintainer workspace.")
        generate.add_argument("--env-file", default=None, help="Optional model configuration file.")
        generate.add_argument(
            "--extraction-json",
            default=None,
            help="Use a prepared extraction JSON instead of invoking the configured model.",
        )

    review = subparsers.add_parser("review", help="Approve or reject a draft, optionally with corrections.")
    review.add_argument("--draft", required=True, help="Draft artifact to review.")
    review.add_argument("--workspace", required=True, help="Private maintainer workspace.")
    review.add_argument("--decision", choices=("approved", "rejected"), required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--notes", default="")
    review.add_argument("--corrections", default=None, help="Optional JSON object merged into extraction fields.")

    publish = subparsers.add_parser("publish", help="Export an approved card without raw source content.")
    publish.add_argument("--reviewed", required=True, help="Approved review artifact.")
    publish.add_argument("--output-dir", required=True, help="Distribution directory.")
    publish.add_argument("--workspace", required=True, help="Private maintainer workspace.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = CasePipeline(args.workspace)
    try:
        if args.command in {"generate", "regenerate"}:
            extractor = (
                JsonFileCaseExtractor(args.extraction_json)
                if args.extraction_json
                else ConfiguredCaseExtractor(args.env_file)
            )
            result = pipeline.generate(args.manifest, extractor)
        elif args.command == "review":
            corrections = None
            if args.corrections:
                corrections = json.loads(Path(args.corrections).read_text(encoding="utf-8-sig"))
            result = pipeline.review(
                args.draft,
                decision=args.decision,
                reviewer=args.reviewer,
                notes=args.notes,
                corrections=corrections,
            )
        else:
            result = pipeline.publish(args.reviewed, args.output_dir)
    except (CasePipelineError, json.JSONDecodeError, OSError) as exc:
        print(f"Case pipeline failed: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": result.status,
                "case_id": result.case_id,
                "revision": result.revision,
                "artifact_path": result.artifact_path.as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
