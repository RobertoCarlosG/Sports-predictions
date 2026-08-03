---
name: e2e-playwright-advisor
description: >
  Analyzes React components and user-described use cases to recommend E2E test scenarios and generate Playwright (.spec.ts) test files. Use this skill whenever the user wants to: plan or write Playwright E2E tests, analyze React components for testability, describe a user flow or use case and get test recommendations, generate .spec.ts test files, or review which interactions in a UI need automated coverage. Trigger even if the user just pastes component code and says something like "what should I test?" or "help me write tests for this". This skill is the right choice any time Playwright, E2E testing, and React components appear together.
---

# E2E Playwright Advisor

A skill for analyzing React components and user-described use cases, recommending E2E test scenarios, and generating Playwright `.spec.ts` test files on request.

---

## Workflow Overview

The skill has **three stages**. Always go through them in order; don't skip ahead.

```
Stage 1: Analyze Components
Stage 2: Understand the Use Case
Stage 3: Recommend Tests → Generate on Request
```

---

## Stage 1: Analyze Components

The user will provide React component source code — either pasted inline or via `@`-tagged files in Claude Code.

### What to extract from each component:

- **Interactive elements**: buttons, inputs, selects, checkboxes, links, forms
- **State changes**: loading states, error states, success messages, conditional rendering
- **Navigation**: route changes, redirects, modal open/close, drawer open/close
- **Data flows**: form submissions, API calls (look for `fetch`, `axios`, `useMutation`, `useQuery`), optimistic updates
- **Auth-gated content**: anything behind a login/role check
- **Accessibility hooks**: `aria-label`, `role`, `data-testid` attributes (note if missing — Playwright relies on these)

### Output of Stage 1:

Produce a **Component Summary** in this format:

```
## Component Analysis

### [ComponentName]
- **Key interactions**: [list]
- **States to cover**: [loading, error, empty, success, etc.]
- **Data dependencies**: [API calls, props, context]
- **Notable selectors**: [data-testid, roles, aria-labels found]
- **Missing testability hooks**: [inputs/buttons without data-testid or accessible names]
```

After the summary, ask: _"Does this look right? Anything I missed? When you're ready, describe the user flow you want to test."_

---

## Stage 2: Understand the Use Case

Ask the user to describe the **full user action** they want to cover — a real use case, not just a feature name.

### Prompt the user with:

> "Describe the flow from the user's perspective — start to finish. For example: 'A logged-in user opens the dashboard, filters the table by date, clicks a row, and downloads a PDF report.' The more detail, the better the test coverage."

### What to extract:

- **Entry point**: Which page/URL does the flow start from?
- **User role**: Anonymous, authenticated, admin, etc.?
- **Steps**: The sequence of interactions
- **Expected outcomes**: What does the user see at the end? (success message, redirect, data updated, etc.)
- **Edge cases mentioned**: What if the form is invalid? What if the API fails?

If the use case is vague, ask one clarifying question at a time. Don't ask more than two follow-ups.

---

## Stage 3: Recommend Tests → Generate on Request

### 3a. Recommendation Report

Based on Stage 1 + Stage 2, produce a **Test Recommendation Report**:

```
## E2E Test Recommendations

### Happy Path
- [Test scenario name]: [What it verifies, why it matters]

### Edge Cases
- [Scenario]: [What it verifies]

### Error States
- [Scenario]: [What it verifies]

### Accessibility / UX checks (optional but recommended)
- [Scenario]: [What it verifies]

---
**Selector readiness**: [Note any missing data-testid or aria-labels that should be added before writing tests]
**Estimated test count**: [N tests]
```

End with: _"Which of these would you like me to generate as a Playwright `.spec.ts` file? I can do all of them or a specific subset."_

---

### 3b. Generate Playwright Tests (on request)

When the user confirms, generate a `.spec.ts` file following the conventions in `references/playwright-conventions.md`.

**Key rules:**
- Use `@playwright/test` imports only
- Use `data-testid` selectors as first preference, then ARIA roles, then visible text — never CSS class selectors
- Group related tests in `test.describe()` blocks
- Each test should have a single clear assertion goal
- Use `page.waitForURL`, `expect(page).toHaveURL()` for navigation assertions
- Mock API calls with `page.route()` when testing error/loading states
- Add a `beforeEach` for auth setup if the flow requires login
- Include comments explaining the intent of non-obvious steps

**File structure:**
```typescript
import { test, expect } from '@playwright/test';

test.describe('[Feature or Component Name]', () => {

  test.beforeEach(async ({ page }) => {
    // setup: navigate to starting URL, login if needed
  });

  test('happy path: [description]', async ({ page }) => {
    // ...
  });

  test('edge case: [description]', async ({ page }) => {
    // ...
  });

});
```

Save the file as `[feature-name].spec.ts` and present it to the user.

---

## Tips for Better Tests

- If the component has **no `data-testid` attributes**, flag this before generating. Suggest adding them to key interactive elements — tests that rely on text content are brittle.
- If the flow requires **authentication**, ask the user if they have a Playwright auth fixture/setup already, or if they want you to include a basic login step inline.
- For **async flows** (form submit → API → redirect), always use `await expect(...)` with Playwright's built-in retry logic, not manual `page.waitForTimeout()`.
- If the user mentions **mobile testing**, add a `devices` config note at the top of the spec.

---

## Reference Files

- `references/playwright-conventions.md` — Detailed Playwright best practices, selector priority, auth patterns, API mocking. Read this before generating any test file.
