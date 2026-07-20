"""Maintainer and local-install CLI for competition experience libraries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data_analysis_agent.experience_library import (  # noqa: E402
    ExperienceLibraryError,
    ExperienceLibraryManager,
    build_experience_package,
    write_library_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, install, inspect, and roll back experience libraries.")
    parser.add_argument("--install-root", default=None, help="Optional isolated version-install directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a checksummed distributable package.")
    build.add_argument("--content-root", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--content-status", choices=("preview", "curated"), required=True)
    build.add_argument("--sources-json", required=True, help="JSON file containing a source inventory list.")

    manifest = subparsers.add_parser("manifest", help="Write a manifest for a bundled content directory.")
    manifest.add_argument("--content-root", required=True)
    manifest.add_argument("--version", required=True)
    manifest.add_argument("--content-status", choices=("preview", "curated"), required=True)
    manifest.add_argument("--sources-json", required=True)

    install = subparsers.add_parser("install", help="Install and activate one package version.")
    install.add_argument("--package", required=True)
    install.add_argument("--no-activate", action="store_true")

    activate = subparsers.add_parser("activate", help="Activate or roll back to an installed version.")
    activate.add_argument("--version", required=True)

    subparsers.add_parser("status", help="Show active/bundled/degraded status and installed versions.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = ExperienceLibraryManager(args.install_root) if args.install_root else ExperienceLibraryManager()
    try:
        if args.command in {"build", "manifest"}:
            sources = json.loads(Path(args.sources_json).read_text(encoding="utf-8-sig"))
            if args.command == "build":
                output = build_experience_package(
                    args.content_root,
                    args.output,
                    version=args.version,
                    content_status=args.content_status,
                    sources=sources,
                )
                result = {"status": "built", "package_path": output.as_posix()}
            else:
                manifest_path = write_library_manifest(
                    args.content_root,
                    version=args.version,
                    content_status=args.content_status,
                    sources=sources,
                )
                result = {"status": "manifested", "manifest_path": manifest_path.as_posix()}
        elif args.command == "install":
            resolution = manager.install(args.package, activate=not args.no_activate)
            result = _resolution_payload(resolution, manager)
        elif args.command == "activate":
            result = _resolution_payload(manager.activate(args.version), manager)
        else:
            result = _resolution_payload(manager.resolve(), manager)
    except (ExperienceLibraryError, OSError, json.JSONDecodeError) as exc:
        print(f"Experience library operation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _resolution_payload(resolution, manager: ExperienceLibraryManager) -> dict[str, object]:
    return {
        "status": resolution.status,
        "version": resolution.version,
        "content_status": resolution.content_status,
        "usable": resolution.usable,
        "installed_versions": list(manager.installed_versions()),
        "warnings": list(resolution.warnings),
    }


if __name__ == "__main__":
    raise SystemExit(main())
