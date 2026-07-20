"""Maintainer CLI for synthesizing reusable modeling skills from case cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.modeling_skills import (  # noqa: E402
    ConfiguredSkillExtractor,
    JsonFileSkillExtractor,
    ModelingSkillBuilder,
    ModelingSkillError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build reusable mathematical-modeling skills from approved case cards.")
    parser.add_argument("--cases", nargs="+", required=True, help="Approved published case-card JSON files.")
    parser.add_argument("--output", required=True, help="Destination catalog JSON file.")
    parser.add_argument("--env-file", default=None, help="Optional model configuration file.")
    parser.add_argument(
        "--skills-json",
        default=None,
        help="Use a prepared {skills: [...]} response instead of invoking the configured model.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    extractor = (
        JsonFileSkillExtractor(args.skills_json)
        if args.skills_json
        else ConfiguredSkillExtractor(args.env_file)
    )
    try:
        output = ModelingSkillBuilder().build(args.cases, extractor, args.output)
    except (ModelingSkillError, OSError) as exc:
        print(f"Modeling skill build failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "built", "catalog_path": output.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
