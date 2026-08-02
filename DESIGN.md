# Academic Agent design system

This application uses a warm editorial product language inspired by the Claude analysis in VoltAgent/awesome-design-md. It adapts that language to a dense, long-lived research workspace rather than reproducing a marketing page.

## Principles

- Calm before decorative: hierarchy comes from typography, spacing, borders, and surface contrast.
- Warm and trustworthy: use cream canvas, warm ink, restrained coral actions, and muted semantic colors.
- Editorial reading: reports and case details use a comfortable reading column and regular-weight serif display headings; controls and body copy use a humanist system sans stack.
- Product first: dark surfaces are reserved for execution logs and technical evidence. Primary coral is scarce and denotes the next meaningful action.
- One visual language: pages share the same shell, header, panel, status, form, table, and empty-state rules.
- Accessible by default: visible focus, sufficient contrast, 40px primary targets, semantic labels, and responsive collapse without hiding core actions.

## Tokens

The canonical implementation is `frontend/src/design-system.css`.

- Canvas: `#F7F3EE`
- Surface: `#FFFDFB`
- Soft surface: `#F4EEE7`
- Ink: `#26221F`
- Muted text: `#6E655F`
- Hairline: `#E4DBD1`
- Primary coral: `#C56F55`
- Dark technical surface: `#1D1B19`
- Spacing: 4, 8, 12, 16, 20, 24, 32, 40, 48px
- Radius: 7px controls, 10px inputs, 14px panels, 18px major work areas
- Elevation: borders first; shadows only for floating overlays and the main composer

## Interface rules

- Sidebar navigation is grouped into workspace actions and resources/settings.
- The top header names the current module, explains its purpose, and exposes only necessary context/actions.
- Main content is capped at 1320px and keeps generous outer breathing room.
- Forms use white/cream fields with coral focus rings; upload inputs share one treatment.
- Reports, case details, and answers prioritize line length and reading rhythm over dashboard density.
- Status is communicated by text and icon as well as color.
- Desktop grids collapse to one or two columns at tablet widths; mobile navigation becomes a cream overlay sheet.

## Avoid

- Cool-blue admin-template styling, gradients, glassmorphism, neon accents, or thick shadows.
- Coral used as decoration rather than action or selection.
- Multiple arbitrary card colors or deeply nested cards with equal visual weight.
- Marketing hero patterns that displace the actual research workflow.
