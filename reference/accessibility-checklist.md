# Accessibility checklist — lookup data

Vendored fallback for auditor 8 in `commands/gate-audit.md` when the `web-design-guidelines`
skill isn't installed. Not a substitute for that skill — it's narrower, covering only the
blocking-tier items `reference/severity-rubric.md` already names (no keyboard access, contrast
failures on core flows) plus the adjacent checks needed to make those judgments: focus
management and semantic HTML. CLAUDE.md's documented accessibility posture overrides anything
here.

## Keyboard access

- Every interactive element (buttons, links, form controls, custom widgets) is reachable and
  operable via `Tab`/`Shift+Tab` alone — no mouse-only handlers (`onClick` with no keyboard
  equivalent, `div`/`span` acting as a button with no `tabindex`/`role`/key handler).
- Tab order follows visual/reading order. No positive `tabindex` values (they override natural
  order and break on reflow).
- No keyboard trap: a user can `Tab` into and back out of every widget, including modals and
  menus (`Escape` closes, focus returns to the trigger).
- Custom widgets (dropdowns, tabs, sliders, comboboxes) implement the expected key set for
  their ARIA role (arrow keys for tabs/menus, `Enter`/`Space` to activate, `Escape` to dismiss).

## Contrast

- Body text and UI text meet **4.5:1** contrast against its background; large text (18pt+, or
  14pt+ bold) meets **3:1**.
- Non-text UI (icon buttons, input borders, focus indicators, chart elements that carry
  meaning) meets **3:1** against adjacent colors.
- Color is never the only signal for state (error, success, required field, disabled) — pair
  it with text, an icon, or a pattern.
- Check both light and dark themes if the surface supports both; a token that passes in one
  can fail in the other.

## Focus management

- Every focusable element has a visible focus indicator (`:focus-visible` outline or
  equivalent) with sufficient contrast against its background — `outline: none` with no
  replacement is a blocking failure.
- Opening a modal/dialog moves focus into it (typically the first focusable element or the
  dialog itself); closing it returns focus to the trigger that opened it.
- Route changes and dynamically injected content (toasts, async-loaded sections) don't strand
  focus on a removed element or silently reset it to `<body>`.
- Skip-link or equivalent exists for bypassing repeated navigation on pages with a persistent
  header/sidebar.

## Semantic HTML

- Structure uses native elements for their purpose (`button` for actions, `a` for navigation,
  `label` for form fields) before reaching for ARIA — ARIA patches meaning onto the wrong
  element; it doesn't beat the right one.
- Every form input has a programmatically associated label (`<label for>`, `aria-label`, or
  `aria-labelledby`) — placeholder text alone is not a label.
- Heading levels (`h1`–`h6`) nest without skipping and reflect actual document structure, not
  visual sizing choices.
- Images that convey information have alt text; purely decorative images have empty
  `alt=""` so screen readers skip them.
- Live regions (`aria-live`) are used for content that updates without a page reload and needs
  to be announced (form errors, async status messages).

## Severity guidance

Map findings using this rubric's own categories, then apply `reference/severity-rubric.md`'s
a11y row:

- **Blocking** — no keyboard path to a core action, a keyboard trap, contrast failure on core
  flow text/controls, missing focus indicator on a primary interactive element.
- **Important** — other contrast/focus/semantic gaps that degrade but don't block task
  completion (secondary content, non-critical flows).
- **Track** — polish (minor heading nesting issues, decorative-image alt text edge cases).
