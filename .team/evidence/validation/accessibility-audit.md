# Accessibility Audit Report — Wizard UI v2.0

**Auditor:** Frontend Engineer (AI Team)
**Date:** 2026-03-02
**Scope:** `wizard/src/` — all 12 wizard steps, UI components, and layout
**Standard:** WCAG 2.1 Level AA

---

## Executive Summary

The wizard UI has a **solid accessibility foundation** with proper ARIA attributes on key interactive elements (Toggle, SelectionCard), keyboard navigation support on selection cards, and semantic HTML structure. Several improvements are recommended for full WCAG 2.1 AA compliance.

**Overall Rating:** B+ (Good — needs minor improvements)

---

## 1. ARIA Attributes on Interactive Elements

### Passing

| Component | Element | ARIA Support | Status |
|-----------|---------|-------------|--------|
| `Toggle` | `<button role="switch">` | `aria-checked={enabled}` | PASS |
| `SelectionCard` | `<div role="button">` | `tabIndex={disabled ? -1 : 0}` | PASS |
| `StepModels` model cards | `<div role="button">` | `tabIndex={0}` | PASS |
| `Button` | `<button>` | Native `disabled` attribute | PASS |
| `Input` (password toggle) | `<button type="button">` | Implicit button semantics | PASS |

### Issues

| ID | Component | Issue | Severity | Recommendation |
|----|-----------|-------|----------|----------------|
| A-01 | `Input` | Label uses `<label>` but is not associated via `htmlFor`/`id` pairing | Medium | Add `id` prop to `<input>` and `htmlFor` to `<label>` |
| A-02 | `SelectionCard` | Missing `aria-label` or `aria-labelledby` — screen readers get no descriptive text for the button role | Medium | Add `aria-label` with the card's title text |
| A-03 | `StepModels` model cards | `role="button"` div lacks `aria-pressed` or `aria-selected` to indicate selection state | Medium | Add `aria-pressed={selected}` to each model card |
| A-04 | `Input` (password) | Eye/EyeOff toggle button has no `aria-label` | Medium | Add `aria-label="Toggle password visibility"` |
| A-05 | `StepFooter` | Navigation buttons lack `aria-label` for screen readers (just "Back" and "Continue" text is acceptable but could include step context) | Low | Consider `aria-label="Go to previous step: Hardware"` |

---

## 2. Keyboard Navigation Support

### Passing

| Component | Behavior | Status |
|-----------|----------|--------|
| `SelectionCard` | Enter/Space activates click handler | PASS |
| `SelectionCard` | `tabIndex={0}` for focusable, `-1` when disabled | PASS |
| `Toggle` | Native `<button>` — focusable and activatable via keyboard | PASS |
| `Button` | Native `<button>` — fully keyboard accessible | PASS |
| `Input` | Native `<input>` — fully keyboard accessible | PASS |
| `StepDeployment` SSH auth buttons | Native `<button type="button">` — keyboard accessible | PASS |

### Issues

| ID | Component | Issue | Severity | Recommendation |
|----|-----------|-------|----------|----------------|
| K-01 | `StepModels` model cards | `role="button"` with `tabIndex={0}` but no `onKeyDown` handler for Enter/Space — clicking via keyboard not supported | High | Add `onKeyDown` handler matching `SelectionCard` pattern |
| K-02 | `Sidebar` | Step list items are not focusable or keyboard-navigable — cannot tab through wizard steps | Medium | Consider making sidebar steps focusable when clickable |
| K-03 | `StepReview` | "Assessment JSON" toggle and "Edit" buttons are keyboard accessible (native buttons), but the JSON code block has no skip mechanism | Low | Add `aria-label` to the toggle and consider `tabIndex={-1}` on the `<pre>` block |

---

## 3. Color Contrast

### Analysis

The wizard uses a dark theme with CSS custom properties. Based on the Tailwind/CSS class patterns:

| Element | Foreground Class | Expected Contrast | Status |
|---------|-----------------|-------------------|--------|
| Primary text | `text-text-primary` | High contrast on dark bg | LIKELY PASS |
| Secondary text | `text-text-secondary` | Medium contrast | NEEDS VERIFICATION |
| Muted text | `text-text-muted` | Low contrast by design | POTENTIAL ISSUE |
| Accent on dark bg | `text-accent` (teal/blue) | Usually passes | LIKELY PASS |
| Error text | `text-error` (red) | Usually passes | LIKELY PASS |
| Warning text | `text-warning` (amber) | Usually passes | LIKELY PASS |
| Badge text | Various badge variants | Depends on bg | NEEDS VERIFICATION |

### Issues

| ID | Component | Issue | Severity | Recommendation |
|----|-----------|-------|----------|----------------|
| C-01 | General | `text-text-muted` on `bg-surface-1` may not meet 4.5:1 contrast ratio for small text (WCAG AA) | Medium | Verify exact hex values; increase brightness if ratio is below 4.5:1 |
| C-02 | `Badge` (muted variant) | Muted badge text on muted background may have insufficient contrast | Low | Verify contrast ratio; consider adding a subtle border for distinction |
| C-03 | `Progress` bar | The progress bar fill (accent on surface background) should be verified for the 3:1 non-text contrast requirement | Low | Verify non-text contrast meets 3:1 ratio |

**Note:** Exact color values are defined in CSS custom properties (likely in `styles/index.css` or Tailwind config). A runtime audit with a tool like axe-core or Lighthouse would provide definitive contrast measurements.

---

## 4. Screen Reader Compatibility

### Passing

| Feature | Implementation | Status |
|---------|---------------|--------|
| Heading hierarchy | `<h1>` in Welcome, `<h3>` in sub-sections | PASS |
| Button semantics | Native `<button>` elements throughout | PASS |
| Switch role | Toggle component uses `role="switch"` with `aria-checked` | PASS |
| Input labels | `<label>` elements for form inputs | PARTIAL (see A-01) |
| Content structure | Logical DOM order matches visual layout | PASS |
| Page title | Set via `<title>` in `index.html` | PASS |

### Issues

| ID | Component | Issue | Severity | Recommendation |
|----|-----------|-------|----------|----------------|
| S-01 | `WizardShell` | No `<main>` landmark wrapping the step content (there is a `<main>` tag, which is good) | N/A | PASS |
| S-02 | `Sidebar` | Sidebar navigation lacks `<nav>` landmark or `role="navigation"` | Medium | Wrap sidebar content in `<nav aria-label="Wizard steps">` |
| S-03 | `StepHeader` | Step progress (e.g., "Step 3 of 12") may not be announced on step change | Medium | Add `aria-live="polite"` region for step progress announcements |
| S-04 | `StepDeploy` | Deployment logs are a live region that should use `aria-live="polite"` for screen reader updates | Medium | Add `aria-live="polite"` and `aria-atomic="false"` to the log container |
| S-05 | `StepDeploy` | Status icons (CheckCircle2, XCircle, etc.) are purely visual — screen readers get no status text | Medium | Add `aria-label` or `sr-only` text alongside each status icon |

---

## 5. Focus Management

### Passing

| Feature | Status |
|---------|--------|
| Focus visible on buttons (outline/ring on focus) | PASS (via Tailwind `focus:ring`) |
| Disabled elements remove from tab order | PASS (via `disabled` attribute or `tabIndex={-1}`) |
| Form inputs have focus styles | PASS (via `focus:border-accent focus:ring-accent`) |

### Issues

| ID | Component | Issue | Severity | Recommendation |
|----|-----------|-------|----------|----------------|
| F-01 | `StepTransition` | When navigating between steps, focus is not moved to the new step content — users must tab from the top | Medium | After step transition, programmatically focus the step heading or first interactive element |
| F-02 | `AnimatePresence` panels | When SSH fields appear or cloud provider API key inputs appear, focus is not moved to the new fields | Low | Consider `autoFocus` on the first new field or use `ref` + `focus()` |

---

## 6. Recommendations Summary (Prioritized)

### High Priority
1. **K-01**: Add keyboard handler to `StepModels` model cards (Enter/Space to toggle selection)

### Medium Priority
2. **A-01**: Associate `<label>` with `<input>` via `htmlFor`/`id` pairing in `Input` component
3. **A-02**: Add `aria-label` to `SelectionCard` instances
4. **A-03**: Add `aria-pressed` to model cards in `StepModels`
5. **A-04**: Add `aria-label` to password toggle button in `Input`
6. **S-02**: Add `<nav>` landmark to `Sidebar`
7. **S-03**: Add `aria-live` region for step progress
8. **S-04**: Add `aria-live` to deployment log container
9. **S-05**: Add screen reader text for status icons
10. **F-01**: Manage focus on step transitions
11. **C-01**: Verify muted text contrast ratio

### Low Priority
12. **A-05**: Enhance footer button labels with step context
13. **C-02**: Verify badge contrast ratios
14. **C-03**: Verify progress bar non-text contrast
15. **F-02**: Auto-focus new fields on dynamic panel appearance
16. **K-02**: Make sidebar steps keyboard-navigable
17. **K-03**: Add skip mechanism for JSON code block

---

## 7. Testing Recommendations

- Run **axe-core** automated scan via `@axe-core/react` in development mode
- Run **Lighthouse** accessibility audit on the built wizard
- Manual testing with **NVDA** (Windows) or **VoiceOver** (macOS) for screen reader compatibility
- Test full wizard flow using **keyboard only** (Tab, Enter, Space, Escape)
- Verify **focus trap** behavior in any modal/dialog components (none found in current wizard)

---

## Appendix: Files Audited

| File | Components | Interactive Elements Checked |
|------|-----------|------------------------------|
| `components/ui/Button.tsx` | Button | onClick, disabled, loading states |
| `components/ui/Input.tsx` | Input | label, password toggle, error/hint |
| `components/ui/Toggle.tsx` | Toggle | role=switch, aria-checked |
| `components/ui/Card.tsx` | Card, SelectionCard, StatCard | role=button, tabIndex, keyboard |
| `components/steps/StepWelcome.tsx` | Welcome step | Input, Button, feature cards |
| `components/steps/StepPlatform.tsx` | Platform step | SelectionCards for each platform |
| `components/steps/StepDeployment.tsx` | Deployment step | SelectionCards, SSH form |
| `components/steps/StepLLM.tsx` | LLM step | Mode selection, provider cards, runtime cards |
| `components/steps/StepModels.tsx` | Models step | Model cards with role=button |
| `components/steps/StepSecurity.tsx` | Security step | Toggle, feature toggles, expand/collapse |
| `components/steps/StepReview.tsx` | Review step | Edit buttons, JSON toggle, import/export |
| `components/steps/StepDeploy.tsx` | Deploy step | Start button, status icons, endpoints |
| `components/layout/WizardShell.tsx` | Shell | Layout structure |
| `components/layout/StepFooter.tsx` | Footer | Back/Continue buttons |
| `components/layout/Sidebar.tsx` | Sidebar | Step navigation |
