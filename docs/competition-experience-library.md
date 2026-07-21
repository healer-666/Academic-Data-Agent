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

## Web browsing, matching, and plan review

The web workspace keeps the two knowledge surfaces separate:

- general analysis continues to show the local knowledge base;
- mathematical modeling changes the same navigation slot to the competition case library.

`GET /api/experience/cases` returns approved case summaries and `GET /api/experience/cases/{case_id}` returns a public detail view with methods, findings, limitations, and metadata-only sources. Private provenance, raw excerpts, checksums, and local paths are never returned.

After a modeling package is reviewed, `POST /api/modeling/packages/{package_id}/plan` matches the current problem statement, user goal, table names, and fields against the active keyword index. Cases below the relevance threshold are not forced into the plan. The same operation selects modeling skills from the versioned catalog and records the considered and selected identifiers in the plan audit block.

The generated plan exposes current-task data operations, historical methods as references rather than conclusions, validation steps, matched-case similarities and differences, selected-skill reasons, source links, and degradation warnings. Users may save adjustments or confirm the plan through `PATCH /api/modeling/packages/{package_id}/plan`; both actions append an auditable event to the modeling package.

## Release maintenance

New historical materials must first pass the Issue #10 extraction and approval gate. Publish only structured cards into a new semantic-version directory, rebuild the keyword index, copy the reviewed modeling-skill catalog, and regenerate `manifest.json` with `experience_library.py manifest`. Build and install a package in an isolated directory before changing the default bundled root.

The next content release should add more reviewed cases and then rebuild modeling skills from the cross-case corpus. Never overwrite user knowledge or place raw problem files, datasets, papers, OCR text, or local paths in a bundled release.
