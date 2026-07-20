# Issue #5: research workspace prototype decision

## Question

Which workspace structure best supports both general data analysis and mathematical modeling projects without creating a second execution product?

The prototypes run on the existing frontend route and are selected with a URL parameter:

- `?variant=A`: staged research pipeline
- `?variant=B`: evidence ledger

Both variants keep state in memory and use fixture content. The default route without `variant` continues to load the backend-connected application.

## Shared workflow coverage

Both variants implement the eight-stage mathematical modeling contract as four reviewable workspace stages:

1. **Materials**: choose general analysis or mathematical modeling, then organize the current project's files.
2. **Plan**: inspect recognized questions, methods, validation, and modeling case inspiration before execution.
3. **Run**: monitor cleaning, exploration, modeling, validation, sensitivity analysis, and packaging.
4. **Results**: inspect evidence-backed conclusions and download either a reproducible analysis report or a competition analysis package.

The mathematical modeling scenario adds problem-package organization, case cards, modeling methods, and competition artifacts. It does not introduce a separate agent or execution path. General analysis does not depend on the competition experience library.

## Variant A: staged research pipeline

### Information architecture

- Global project type switch and project identity
- Persistent left workflow navigation for materials, plan, run, and results
- Central stage workspace with one clear primary action
- Right project-health panel for completeness, risk, and evidence coverage
- On-demand evidence inspector for source data, code, and lineage

### Visual principles

- Quiet, light research environment with restrained green, cyan, and amber status colors
- Strong stage hierarchy and generous working area, without decorative dashboard cards
- Progressive disclosure: advanced evidence appears in a drawer instead of competing with the task
- Mobile layout turns the workflow rail into a drawer and preserves the current stage as the primary surface

### Strengths

- Makes the required review gate between plan and execution explicit
- Works well for first-time and occasional users
- Keeps general analysis and mathematical modeling visibly related
- Has the clearest path to the existing backend-connected application

## Variant B: evidence ledger

### Information architecture

- Compact command header and horizontal stage register
- Table-oriented material, method, run, and finding ledgers
- Persistent run status dock
- Evidence inspector shown beside findings on wide viewports

### Visual principles

- Dense operational surface inspired by lab registers and audit consoles
- Dark command chrome paired with neutral data sheets
- Rows, columns, and status fields favor scanning and comparison over guided explanation
- Mobile layout preserves tables through controlled horizontal scrolling

### Strengths

- High information density for experienced teams
- Makes method, validation, run, and evidence status easy to compare
- Provides useful patterns for the future run history and audit views

## Decision

**Variant A, the staged research pipeline, is user-confirmed as the product direction.**

It best fits the confirmed scenario contract: users can understand that mathematical modeling is an enhancement of the same analysis workflow, and the plan-confirmation gate is visible before execution. Its information hierarchy also adapts more naturally to mobile screens and the current backend API.

This decision confirms the information architecture and workflow, not the current visual finish. Visual refinement is intentionally deferred to a later iteration; the present prototype should not be treated as the final design system or production styling reference.

The implementation should borrow two ideas from Variant B:

- use compact register rows in method review and run history when comparison is more important than explanation;
- keep evidence coverage visible as a first-class status, not only inside the final report.

The prototype files remain isolated under `frontend/src/prototype/` as the primary design source. They are not production components and should be removed when the selected structure is implemented in the backend-connected application.

## Deferred visual refinement

The follow-up visual pass should preserve Variant A's structure while revisiting typography, spacing rhythm, control hierarchy, color balance, data-visualization treatment, and the visual relationship between the central workspace and evidence inspector. These changes should improve perceived quality without reopening the selected workflow or splitting mathematical modeling into a separate product.
