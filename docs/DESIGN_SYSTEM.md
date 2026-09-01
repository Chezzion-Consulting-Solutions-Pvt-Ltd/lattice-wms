# Lattice Design System

## Figma Reference

Approved visual source of truth:

https://www.figma.com/design/qXi6XQBQyB4IxccNEUrx3H/WMS?node-id=412-302&p=f&t=dfZR9pTgOnASPzm7-0

Programmatic inspection was attempted on 2026-08-31 using the Figma MCP `get_design_context` and `get_metadata` tools. The file and node returned `INVALID_ARGUMENT`, so exact Figma values could not be extracted in this session.

Until Figma access is corrected, Lattice uses centralized provisional tokens only. Do not add guessed colors or arbitrary component styles directly to pages.

## Official Frontend Stack

- React + TypeScript
- Tailwind CSS
- Radix UI primitives where useful
- Lattice Design System

Tailwind is an implementation utility, not the visual design system. Figma and Lattice semantic design tokens remain the visual source of truth.

Radix UI is used for accessible behavior primitives such as dialogs, alert dialogs, dropdowns, popovers, tooltips, tabs, selects, checkboxes, radio groups, and switches. Radix primitives must be wrapped in Lattice components so feature pages consume Lattice UI rather than raw primitive APIs.

## Principles

- Figma controls presentation.
- The Secure Core architecture controls authentication, authorization, tenant isolation, database routing, audit, and business logic.
- Frontend permission-aware navigation is UX only.
- Shared components come before feature pages.
- WMS tables are first-class interface surfaces.

## Token Architecture

Tokens live in:

- `frontend/src/styles/tokens.css`
- `frontend/src/styles/typography.css`
- `frontend/src/styles/globals.css`
- `frontend/src/design-system/tokens/index.ts`
- Tailwind v4 theme tokens in `frontend/src/styles/globals.css`

Semantic CSS variables include color, spacing, radius, shadow, layout, and typography values. Replace provisional values with exact Figma values only in these files.

Tailwind semantic utilities are mapped to existing variables, for example `bg-lattice-primary`, `bg-lattice-surface`, `text-lattice-text-primary`, and `border-lattice-border`. Do not use repeated arbitrary Tailwind color values in feature pages.

## Components

Current shared components:

- `AppShell`
- `Button`
- `IconButton`
- `Input`
- `SearchInput`
- `PasswordInput`
- `TextArea`
- `Select`
- `Checkbox`
- `RadioGroup`
- `Switch`
- `Card`
- `StatCard`
- `Badge`
- `StatusBadge`
- `DataTable`
- `Dialog`
- `ConfirmationDialog`
- `DropdownMenu`
- `Popover`
- `Tooltip`
- `Tabs`
- `PageHeader`
- `Sidebar`
- `Topbar`
- `EmptyState`
- `LoadingState`
- `ErrorState`

Owner Console work in this milestone continues to reuse the shared shell, buttons, badges, stat cards, data table, page header, Radix-backed wrappers, and centralized CSS tokens. Screen polish must stay inside those shared primitives or Owner Console-specific CSS and must not introduce a separate theme.

Planned next components include drawer, breadcrumb, table column visibility, table filter chips, toast, and skeleton.

## Status System

| Business Status | Semantic Variant |
| --- | --- |
| CREATED | info |
| IN_PROGRESS | info |
| PENDING | warning |
| COMPLETED | success |
| CANCELLED | danger |
| BLOCKED | warning |
| FAILED | danger |
| WARNING | warning |

## Responsive Rules

Lattice is desktop-first for enterprise warehouse operations. Smaller screens should remain usable where reasonable, but tables must not be converted into unreadable cards. Use controlled horizontal scrolling, adaptive sidebars, and drawers.

## Accessibility Rules

- Keep visible focus states.
- Label form controls.
- Use accessible names for icon-only buttons.
- Do not use color alone to convey status.
- Preserve reasonable contrast when replacing provisional tokens with Figma values.
## Tenant Admin UI

Tenant admin pages reuse the shared Lattice shell, cards, buttons, dialogs, data tables, form fields, status badges, and centralized tokens. Hierarchy screens keep dense records in readable tables and use tokenized glass styling selectively for the shell and summary cards.
