# Runtime mathematical-modeling skills

Issue #11 introduces project-internal runtime skills: reusable mathematical-modeling methods synthesized from multiple approved case cards. They are ordinary project data and Python interfaces, not Codex `SKILL.md` plugins.

## What a skill contains

Every skill is organized by method rather than paper or competition. Its contract includes:

- applicability: supported task types, matching data characteristics and exclusions;
- inputs and outputs: named artifacts the caller must provide or can expect;
- procedure: ordered actions and their purposes;
- validation requirements: observable checks that must accompany the method;
- `source_case_ids`: at least two approved cases supporting the reusable pattern.

The six catalog categories are data diagnostics, feature engineering, modeling, validation, sensitivity analysis, and result organization. The synthesis source catalog is at `data/modeling_skills/catalog.json`; runtime modeling tasks resolve the active versioned experience library described in `docs/competition-experience-library.md`.

## Build from approved cases

Case cards must first pass the Issue #10 review and publish flow. Build a catalog from two or more published cards:

```powershell
python modeling_skills.py `
  --cases library/case-a.json library/case-b.json `
  --output data/modeling_skills/catalog.json
```

For a deterministic or human-reviewed extraction, pass a prepared JSON object containing `{"skills": [...]}`:

```powershell
python modeling_skills.py `
  --cases library/case-a.json library/case-b.json `
  --skills-json reviewed-skills.json `
  --output data/modeling_skills/catalog.json
```

The build fails if a case is unpublished or unapproved, a skill cites fewer than two cases, a skill omits its interface fields, or the resulting catalog does not cover all six categories.

## Runtime selection

`ModelingSkillCatalog.select()` takes a `ModelingTaskProfile` and deterministically scores applicable methods using the task type, query, columns, shape, and inferred or explicit characteristics. It returns the selected methods with scores and reasons. `run_analysis()` invokes this selector only when `task_type="mathematical_modeling"`; ordinary analysis tasks are unchanged.

The selected methods are rendered into the model context as method constraints and checklists. The context explicitly forbids treating historical case findings as current evidence or results.

Callers can override the catalog or provide task characteristics:

```python
result = run_analysis(
    "current_problem.csv",
    query="Forecast demand and optimize capacity",
    task_type="mathematical_modeling",
    modeling_skill_catalog_path="data/modeling_skills/catalog.json",
    modeling_characteristics=("time_series", "optimization"),
)
```

The representative tests cover time-series demand/capacity tasks and validate that all selected core methods have cross-case provenance, explicit inputs and outputs, and observable validation requirements.
