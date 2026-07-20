"""Versioned competition experience-library packaging and local activation.

The library is stored separately from user knowledge and project memory.  A
validated version is immutable after installation; upgrades install another
version and move only the small active-version pointer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "1.0"
LIBRARY_ID = "academic-data-agent-competition-experience"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INSTALL_ROOT = PROJECT_ROOT / "memory" / "competition_experience_library"
DEFAULT_BUNDLED_ROOT = PROJECT_ROOT / "data" / "competition_experience" / "bundled" / "preview-0.1.0"
ALLOWED_CONTENT_STATUS = frozenset({"preview", "curated"})
ALLOWED_ARTIFACT_KINDS = frozenset({"case_card", "keyword_index", "modeling_skills", "metadata"})
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


class ExperienceLibraryError(ValueError):
    """Raised when a package or requested activation is invalid."""


@dataclass(frozen=True)
class ExperienceLibraryResolution:
    """Runtime-safe view of the active, bundled, or degraded library."""

    status: str
    version: str = ""
    content_status: str = ""
    library_root: Path | None = None
    skill_catalog_path: Path | None = None
    keyword_index_path: Path | None = None
    case_card_paths: tuple[Path, ...] = ()
    source_inventory: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.status in {"active", "bundled"} and self.library_root is not None


class ExperienceLibraryManager:
    """Install immutable versions, activate one, and resolve it for runtime use."""

    def __init__(
        self,
        install_root: str | Path = DEFAULT_INSTALL_ROOT,
        bundled_root: str | Path | None = DEFAULT_BUNDLED_ROOT,
    ) -> None:
        self.install_root = Path(install_root).resolve()
        self.bundled_root = Path(bundled_root).resolve() if bundled_root is not None else None
        self.versions_root = self.install_root / "versions"
        self.active_pointer = self.install_root / "active.json"

    def install(self, package_path: str | Path, *, activate: bool = True) -> ExperienceLibraryResolution:
        package = Path(package_path).resolve()
        if not package.is_file():
            raise ExperienceLibraryError(f"Experience-library package does not exist: {package}")
        self.versions_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="install-", dir=self.install_root)).resolve()
        try:
            _safe_extract(package, staging)
            manifest = _validate_library_directory(staging, require_curated_cases=False)
            version = manifest["library"]["version"]
            destination = (self.versions_root / version).resolve()
            _require_child(destination, self.versions_root)
            if destination.exists():
                existing = _validate_library_directory(destination, require_curated_cases=False)
                if existing != manifest:
                    raise ExperienceLibraryError(f"Version {version} is already installed with different content.")
            else:
                os.replace(staging, destination)
            if activate:
                self.activate(version)
            return _resolution_from_directory(destination, status="active" if activate else "installed")
        finally:
            if staging.exists():
                _require_child(staging, self.install_root)
                shutil.rmtree(staging)

    def activate(self, version: str) -> ExperienceLibraryResolution:
        normalized_version = _normalize_version(version)
        version_root = (self.versions_root / normalized_version).resolve()
        _require_child(version_root, self.versions_root)
        _validate_library_directory(version_root, require_curated_cases=False)
        self.install_root.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(
            self.active_pointer,
            {"schema_version": SCHEMA_VERSION, "active_version": normalized_version, "activated_at": _utc_now()},
        )
        return _resolution_from_directory(version_root, status="active")

    def resolve(self) -> ExperienceLibraryResolution:
        """Resolve without raising; invalid state degrades to general analysis."""

        if self.active_pointer.exists():
            try:
                pointer = _read_json(self.active_pointer)
                version = _normalize_version(pointer.get("active_version", ""))
                version_root = (self.versions_root / version).resolve()
                _require_child(version_root, self.versions_root)
                return _resolution_from_directory(version_root, status="active")
            except (ExperienceLibraryError, OSError, json.JSONDecodeError) as exc:
                return ExperienceLibraryResolution(
                    status="degraded",
                    warnings=(f"Installed competition experience library is unavailable: {exc}",),
                )

        if self.bundled_root is not None:
            try:
                return _resolution_from_directory(self.bundled_root, status="bundled")
            except (ExperienceLibraryError, OSError, json.JSONDecodeError) as exc:
                return ExperienceLibraryResolution(
                    status="degraded",
                    warnings=(f"Bundled competition experience library is unavailable: {exc}",),
                )
        return ExperienceLibraryResolution(
            status="degraded",
            warnings=("No competition experience library is installed or bundled; using general analysis.",),
        )

    def installed_versions(self) -> tuple[str, ...]:
        if not self.versions_root.exists():
            return ()
        versions: list[str] = []
        for path in self.versions_root.iterdir():
            if not path.is_dir():
                continue
            try:
                versions.append(_validate_library_directory(path, require_curated_cases=False)["library"]["version"])
            except ExperienceLibraryError:
                continue
        return tuple(sorted(set(versions), key=_version_sort_key, reverse=True))


def build_experience_package(
    content_root: str | Path,
    output_path: str | Path,
    *,
    version: str,
    content_status: str,
    sources: Iterable[Mapping[str, Any]],
    published_at: str | None = None,
) -> Path:
    """Create a self-contained, checksummed package from reviewed content."""

    root = Path(content_root).resolve()
    if not root.is_dir():
        raise ExperienceLibraryError(f"Experience content root does not exist: {root}")
    normalized_version = _normalize_version(version)
    normalized_status = str(content_status or "").strip().lower()
    if normalized_status not in ALLOWED_CONTENT_STATUS:
        raise ExperienceLibraryError("content_status must be 'preview' or 'curated'.")
    normalized_sources = _normalize_sources(list(sources))
    artifacts = _collect_artifacts(root)
    _validate_required_artifacts(artifacts, content_status=normalized_status)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "library": {
            "id": LIBRARY_ID,
            "version": normalized_version,
            "content_status": normalized_status,
            "published_at": str(published_at or _utc_now()),
        },
        "sources": normalized_sources,
        "artifacts": artifacts,
    }
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for artifact in artifacts:
            archive.write(root / artifact["path"], artifact["path"])
    return destination


def write_library_manifest(
    content_root: str | Path,
    *,
    version: str,
    content_status: str,
    sources: Iterable[Mapping[str, Any]],
    published_at: str | None = None,
) -> Path:
    """Write a checksummed manifest for a read-only bundled directory."""

    root = Path(content_root).resolve()
    artifacts = _collect_artifacts(root)
    normalized_status = str(content_status or "").strip().lower()
    if normalized_status not in ALLOWED_CONTENT_STATUS:
        raise ExperienceLibraryError("content_status must be 'preview' or 'curated'.")
    _validate_required_artifacts(artifacts, content_status=normalized_status)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "library": {
            "id": LIBRARY_ID,
            "version": _normalize_version(version),
            "content_status": normalized_status,
            "published_at": str(published_at or _utc_now()),
        },
        "sources": _normalize_sources(list(sources)),
        "artifacts": artifacts,
    }
    path = root / "manifest.json"
    _write_json_atomic(path, manifest)
    return path


def _resolution_from_directory(root: Path, *, status: str) -> ExperienceLibraryResolution:
    manifest = _validate_library_directory(root, require_curated_cases=False)
    by_kind: dict[str, list[Path]] = {}
    for artifact in manifest["artifacts"]:
        by_kind.setdefault(artifact["kind"], []).append((root / artifact["path"]).resolve())
    return ExperienceLibraryResolution(
        status=status,
        version=manifest["library"]["version"],
        content_status=manifest["library"]["content_status"],
        library_root=root.resolve(),
        skill_catalog_path=_first(by_kind.get("modeling_skills", [])),
        keyword_index_path=_first(by_kind.get("keyword_index", [])),
        case_card_paths=tuple(by_kind.get("case_card", [])),
        source_inventory=tuple(manifest["sources"]),
    )


def _validate_library_directory(root: Path, *, require_curated_cases: bool) -> dict[str, Any]:
    directory = root.resolve()
    manifest = _read_json(directory / "manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ExperienceLibraryError(f"Unsupported experience-library schema: {manifest.get('schema_version')}")
    library = manifest.get("library")
    if not isinstance(library, Mapping) or library.get("id") != LIBRARY_ID:
        raise ExperienceLibraryError("Experience-library manifest has an invalid library id.")
    version = _normalize_version(library.get("version", ""))
    content_status = str(library.get("content_status", "") or "").strip().lower()
    if content_status not in ALLOWED_CONTENT_STATUS:
        raise ExperienceLibraryError("Experience-library content status is invalid.")
    sources = _normalize_sources(manifest.get("sources"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ExperienceLibraryError("Experience-library manifest requires artifacts.")
    normalized_artifacts: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for raw in artifacts:
        artifact = _normalize_artifact(raw)
        if artifact["path"] in seen_paths:
            raise ExperienceLibraryError(f"Duplicate artifact path: {artifact['path']}")
        seen_paths.add(artifact["path"])
        path = (directory / artifact["path"]).resolve()
        _require_child(path, directory)
        if not path.is_file():
            raise ExperienceLibraryError(f"Experience-library artifact is missing: {artifact['path']}")
        if path.stat().st_size != artifact["size_bytes"] or _sha256(path) != artifact["sha256"]:
            raise ExperienceLibraryError(f"Experience-library artifact failed integrity check: {artifact['path']}")
        normalized_artifacts.append(artifact)
    actual_paths = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    unlisted = sorted(actual_paths - seen_paths)
    if unlisted:
        raise ExperienceLibraryError("Experience-library directory contains unlisted artifacts: " + ", ".join(unlisted))
    _validate_required_artifacts(
        normalized_artifacts,
        content_status="curated" if require_curated_cases else content_status,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "library": {
            "id": LIBRARY_ID,
            "version": version,
            "content_status": content_status,
            "published_at": str(library.get("published_at", "") or "").strip(),
        },
        "sources": sources,
        "artifacts": normalized_artifacts,
    }


def _collect_artifacts(root: Path) -> list[dict[str, Any]]:
    kinds = {"cases": "case_card", "indexes": "keyword_index", "skills": "modeling_skills"}
    artifacts: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        top_level = PurePosixPath(relative).parts[0] if PurePosixPath(relative).parts else ""
        kind = kinds.get(top_level, "metadata")
        artifacts.append(
            {"path": relative, "kind": kind, "sha256": _sha256(path), "size_bytes": path.stat().st_size}
        )
    return artifacts


def _validate_required_artifacts(artifacts: Iterable[Mapping[str, Any]], *, content_status: str) -> None:
    kinds = {str(item.get("kind", "")) for item in artifacts}
    missing = {"modeling_skills", "keyword_index"} - kinds
    if content_status == "curated":
        if "case_card" not in kinds:
            missing.add("case_card")
    if missing:
        raise ExperienceLibraryError("Experience library is missing required artifacts: " + ", ".join(sorted(missing)))


def _normalize_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ExperienceLibraryError("Experience-library sources must be a list.")
    if not value:
        raise ExperienceLibraryError("Experience-library sources must not be empty.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise ExperienceLibraryError(f"Experience-library source #{index} must be an object.")
        required = {key: str(item.get(key, "") or "").strip() for key in ("id", "title", "kind", "license")}
        if not all(required.values()):
            raise ExperienceLibraryError(f"Experience-library source #{index} requires id, title, kind, and license.")
        normalized.append({**required, "uri": str(item.get("uri", "") or "").strip()})
    return normalized


def _normalize_artifact(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExperienceLibraryError("Every experience-library artifact must be an object.")
    path = _safe_relative_path(value.get("path", ""))
    kind = str(value.get("kind", "") or "").strip()
    if kind not in ALLOWED_ARTIFACT_KINDS:
        raise ExperienceLibraryError(f"Unsupported experience-library artifact kind: {kind}")
    sha256 = str(value.get("sha256", "") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ExperienceLibraryError(f"Invalid checksum for artifact: {path}")
    try:
        size_bytes = int(value.get("size_bytes", -1))
    except (TypeError, ValueError) as exc:
        raise ExperienceLibraryError(f"Invalid size for artifact: {path}") from exc
    if size_bytes < 0:
        raise ExperienceLibraryError(f"Invalid size for artifact: {path}")
    return {"path": path, "kind": kind, "sha256": sha256, "size_bytes": size_bytes}


def _safe_extract(package: Path, destination: Path) -> None:
    try:
        archive = zipfile.ZipFile(package, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ExperienceLibraryError(f"Invalid experience-library package: {exc}") from exc
    with archive:
        for member in archive.infolist():
            relative = _safe_relative_path(member.filename)
            target = (destination / relative).resolve()
            _require_child(target, destination)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _safe_relative_path(value: Any) -> str:
    text = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or ":" in text:
        raise ExperienceLibraryError(f"Unsafe experience-library path: {value}")
    return path.as_posix()


def _require_child(path: Path, parent: Path) -> None:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError as exc:
        raise ExperienceLibraryError(f"Path escapes experience-library root: {path}") from exc


def _normalize_version(value: Any) -> str:
    version = str(value or "").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ExperienceLibraryError(f"Invalid experience-library version: {version or '<empty>'}")
    return version


def _version_sort_key(value: str) -> tuple[int, int, int, bool, str]:
    core, _, suffix = value.partition("-")
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch, not bool(suffix), suffix


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ExperienceLibraryError(f"Experience-library manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExperienceLibraryError(f"Experience-library JSON is invalid: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExperienceLibraryError(f"Experience-library JSON must be an object: {path}")
    return payload


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def _first(values: list[Path]) -> Path | None:
    return values[0] if values else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
