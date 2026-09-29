# 0008 — Styling with Tailwind CSS

## Status

Accepted

## Context

The auth pages (E1.3) are ReNest's first designed UI. Before them, the
frontend had no styling at all: the listing pages render with browser
defaults. Every page after E1.3 (the nav bar, the Account tab, browsing and
posting listings) will reuse the same colors, type, spacing, and components,
so the styling approach picked now is the one the rest of the app is built
on.

The constraints:

- **The designs live in Figma**, with specific colors, font sizes, spacing,
  and corner radii that pages must match. Those values need to be defined
  once and reused, not retyped per page.
- **Three people, one semester.** Whatever we pick has to be quick to learn
  and hard to misuse, and reviewers need to be able to spot a one-off style
  that bypasses the shared design values.
- **Mobile first.** Most students will use ReNest on their phones, so
  responsive layout has to be easy, not an afterthought.
- **The existing stack** is Vite + React + TypeScript (ADR 0003). The styling
  choice shouldn't need a different build setup or a runtime library.

## Decision

Style the frontend with **Tailwind CSS v4**, added through its official Vite
plugin (`@tailwindcss/vite`).

- **Design values are defined once, in CSS.** `frontend/src/index.css`
  declares the Figma values in a Tailwind `@theme` block: colors named by
  their job (`bg`, `surface`, `text`, `text-muted`, `accent`, `danger`,
  `success`, `border`, plus a few tints), the fonts (Geist, Instrument Sans),
  the extra font sizes, and the corner radii. Tailwind turns each one into
  classes, e.g. `bg-accent`, `text-text-muted`, `rounded-lg`.
- **Colors are named by job, not shade.** A button is `bg-accent`, not
  `bg-blue-700`. If the accent color changes, it changes in one place.
- **Pages are built from shared components** in `frontend/src/components/`
  (`Button`, `TextField`, `Alert`, `AuthLayout`, `TextLink`), not from
  one-off class lists. Raw hex colors and arbitrary color values (`[#...]`)
  don't belong in components or pages. That's easy to check in review with a
  search.
- **Fonts are self-hosted** through Fontsource (`@fontsource-variable/*`), so
  pages make no requests to Google Fonts.

## Alternatives Considered

**CSS Modules** (one `.module.css` file per component, with CSS variables for
the design values). The main alternative, and a reasonable one. Rejected
because:

- Every component becomes two files, and the class names in the CSS file and
  the JSX have to be kept in sync by hand.
- The "is this using the shared design values?" question gets harder to
  answer in review. With Tailwind, a design value is either a named theme
  class or a visibly odd arbitrary value. With CSS Modules, a hard-coded
  `#1d4ed8` hides inside a separate file.
- Responsive rules need hand-written media queries. Tailwind's `sm:` / `md:`
  prefixes keep the mobile and desktop versions of a style side by side.

**Plain global CSS.** Rejected: with no scoping, class names collide as the
app grows, and nothing stops a style for one page from leaking into another.

**A component library** (MUI, Chakra, shadcn/ui). Rejected for now: these
bring their own visual design, which we'd spend time overriding to match
Figma, and (for MUI and Chakra) a runtime and a much larger bundle. The
handful of components the auth pages need were quicker to build than to
restyle. shadcn/ui is itself built on Tailwind, so this decision keeps the
door open if we want its more complex components (dialogs, menus) later.

**Tailwind v3** (configured in `tailwind.config.js`). Rejected in favor of v4,
the current version: v4 is configured directly in CSS with no separate JS
config file, and its Vite plugin needs no PostCSS setup.

## Consequences

- **Preflight.** Tailwind's base reset removes browser default styles
  everywhere, including on the unstyled listing pages. `index.css` has a
  small fallback that gives unclassed inputs and buttons a visible border, so
  those pages stay usable until they're designed. Delete it once no unclassed
  form controls remain.
- **Class-heavy markup.** Components carry long `className` strings. This is
  the trade-off for having styles next to the markup. Repeated patterns
  belong in a shared component, not copy-pasted class lists.
- **Design changes go through the theme.** A new color or size from Figma
  should be added to the `@theme` block with a job-based name, not used as an
  arbitrary value in a component.
- **Deliberate deviations from Figma** are recorded where they're made: in the
  E1.3 design notes and in comments next to the tokens. The first two are
  input text raised from 15px to 16px (so iPhones don't zoom in on focus) and
  a darker red for error text (for WCAG AA contrast).
- **Revisit if** the team adopts a component library that ships its own
  styling system, or if the design moves to a token pipeline (e.g. Figma
  variables exported automatically), which would change where theme values
  come from but not the choice of Tailwind.
