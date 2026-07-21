# Versioned competition experience library

Issue #12 packages approved case cards, retrieval indexes, and modeling skills as a separately versioned competition experience library. The default bundled library is now the first curated release; raw historical files remain in the private maintainer workspace.

## Current content status

The bundled version is `1.0.0` with `content_status: curated`. It contains:

- the mathematical-modeling skill catalog from Issue #11;
- five source-backed retrieval chunks for the 2022 CUMCM C problem;
- the approved, structured `cumcm-2022-c` case card derived from the problem, its workbook, and papers C155 and C229;
- a checksummed manifest and source inventory.

Ordinary installations can use this content without importing historical files. The original problem PDF, workbook, paper images, and OCR text are not bundled. The earlier `0.1.0-preview` directory remains in the repository as a lifecycle fixture but is no longer the default runtime fallback.

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

For mathematical-modeling runs, the runtime resolves an installed active version first and otherwise uses bundled `1.0.0`. It validates the manifest and all artifact checksums before loading methods. If the active pointer, package, or skill catalog is missing or damaged, the run continues as general analysis without historical-case guidance. An explicitly supplied skill catalog remains strict and reports errors instead of silently degrading.

## Release maintenance

New historical materials must first pass the Issue #10 extraction and approval gate. Publish only structured cards into a new semantic-version directory, rebuild the keyword index, copy the reviewed modeling-skill catalog, and regenerate `manifest.json` with `experience_library.py manifest`. Build and install a package in an isolated directory before changing the default bundled root.

The next content release should add more reviewed cases and then rebuild modeling skills from the cross-case corpus. Never overwrite user knowledge or place raw problem files, datasets, papers, OCR text, or local paths in a bundled release.
