# Academic Agent design system

Academic Agent uses a quiet, conversation-first workspace language. The interface should feel like an AI tool: one clear action at a time, generous whitespace, document-style output, and progressive disclosure for technical detail.

## Principles

- The page background is the default container. Add a surface only when the object is independently interactive or floating.
- New analysis has one focal point: the composer. Mode, attachments, and submit actions live inside or immediately around it.
- Use typography, alignment, spacing, and hairlines before cards, borders, color, or shadow.
- Keep product copy short. Internal workflow, audit, and implementation detail stays collapsed until requested.
- Reports and case details use a reading column; history uses a conversation column; lineage gets a dedicated canvas.
- Preserve every business action while shortening the path to it.

## Tokens

The canonical implementation is `frontend/src/design-system.css`.

- Background: `#f8f7f4`
- Sidebar: `#f1efe9`
- Surface: `#ffffff`
- Subtle surface: `#f3f1ec`
- Primary text: `#24221f`
- Secondary text: `#6f6b64`
- Hairline: `rgba(36, 34, 31, 0.10)`
- Accent: `#cc785c`, reserved for primary actions and limited state
- Radius: 8–10px for controls, 18–24px for the main composer
- Elevation: none by default; only menus, drawers, dialogs, and the composer may use a light shadow
- Motion: 150ms for controls and 200ms for layout, always `ease-out`

## Interface rules

- Desktop sidebar is 264px expanded and 60px collapsed. The expand control remains in the main layout when the sidebar is collapsed.
- Mobile sidebar is a dismissible drawer with backdrop, Escape support, and scroll lock.
- The top bar contains only the sidebar control, page name, meaningful task status, files, and refresh.
- New analysis uses a light segmented control and a single 900px composer with an attachment menu and per-file removal.
- Results use tabs and document flow. Logs, audit detail, and source evidence are progressively disclosed.
- History uses a compact task list, direct document/assistant content, and a sticky composer.
- Case library uses a master-detail reading layout; knowledge uses a file table; settings use categories and divided sections.

## Avoid

- Dashboard card walls, nested cards, decorative English kickers, oversized marketing titles, or explanatory process panels.
- Large dark blocks, saturated accent coverage, thick shadows, gradients, glass effects, and ornamental icons.
- Showing raw logs, internal policies, or audit mechanics before the user asks for them.
