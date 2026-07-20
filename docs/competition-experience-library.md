# Versioned competition experience library

Issue #12 packages approved case cards, retrieval indexes, and modeling skills as a separately versioned competition experience library. This first phase implements the lifecycle and ships only preview fixtures; real historical competition materials will be added later.

## Current content status

The bundled version is `0.1.0-preview`. Its manifest explicitly declares `content_status: preview` and lists `representative-method-fixtures` as its only source. It contains:

- the representative modeling-skill catalog from Issue #11;
- an empty keyword retrieval index;
- no real historical case cards, problems, datasets, or papers.

It exists so ordinary installations can exercise the complete resolution path without importing files. It must not be described as a curated historical experience library. The first real release should use `content_status: curated` and include at least one approved case card; the planned `v1.0.0` should contain the agreed first batch of reviewed cases.

## Package contract

Every directory or distributable archive contains `manifest.json` with:

- a semantic version, publication time, and `preview` or `curated` status;
- a source inventory with identifier, title, kind, license, and optional URI;
- every artifact's relative path, kind, byte size, and SHA-256 checksum.

Packages reject absolute paths, parent-directory traversal, missing required artifacts, invalid checksums, and duplicate paths. A curated package additionally requires at least one case card.

## Install, upgrade, and rollback

Build a self-contained archive:

```powershell
python experience_library.py build `
  --content-root reviewed-library-content `
  --output releases/competition-experience-1.0.0.zip `
  --version 1.0.0 `
  --content-status curated `
  --sources-json reviewed-library-sources.json
```

Install and activate it:

```powershell
python experience_library.py install `
  --package releases/competition-experience-1.0.0.zip
```

Each installed version remains immutable under `memory/competition_experience_library/versions/`. Upgrading installs another directory and updates only `active.json`. Roll back without deleting the newer version:

```powershell
python experience_library.py activate --version 1.0.0
```

Inspect the active or fallback state:

```powershell
python experience_library.py status
```

## User-data isolation and degradation

The built-in library directory is separate from `memory/knowledge_base`, `memory/project_memory`, and `memory/failure_memory`. Install, upgrade, and rollback operations never write to those user-owned stores.

For mathematical-modeling runs, the runtime resolves an installed active version first and otherwise uses the bundled preview. It validates the manifest and all artifact checksums before loading methods. If the active pointer, package, or skill catalog is missing or damaged, the run continues as general analysis without historical-case guidance. An explicitly supplied skill catalog remains strict and reports errors instead of silently degrading.

## Remaining work for Issue #12

- upload the first real historical problems, data attachments, and high-quality papers;
- generate and approve case cards through the Issue #10 pipeline;
- rebuild modeling skills from the real cross-case corpus;
- create a populated retrieval index;
- publish and test the first curated experience-library release.
