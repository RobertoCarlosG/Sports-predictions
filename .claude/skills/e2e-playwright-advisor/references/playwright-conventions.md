# Playwright Conventions Reference

Detailed best practices for generating Playwright E2E tests in `.spec.ts` format.

---

## Selector Priority (most to least preferred)

1. `page.getByTestId('my-element')` → requires `data-testid="my-element"` on the element
2. `page.getByRole('button', { name: 'Submit' })` → ARIA role + accessible name
3. `page.getByLabel('Email address')` → for form inputs with associated labels
4. `page.getByText('Confirm')` → visible text (OK for static labels, fragile for dynamic content)
5. `page.locator('input[name="email"]')` → attribute selectors (acceptable fallback)
6. ❌ `page.locator('.submit-btn')` → CSS classes — **never use**, they change with refactors

**Rule**: If a component lacks `data-testid` on key interactive elements, note this as a testability gap in the recommendation report.

---

## File Structure Template

```typescript
import { test, expect } from '@playwright/test';

// Optional: import fixtures or helpers
// import { loginAs } from '../fixtures/auth';

test.describe('FeatureName - [brief description]', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/your-route');
    // Add login or state setup here if needed
  });

  test('happy path: user can [do the main thing]', async ({ page }) => {
    // Arrange: set up any pre-conditions
    // Act: perform user interactions
    // Assert: verify the expected outcome
  });

  test('error state: shows error when [condition]', async ({ page }) => {
    // Mock the failing API
    await page.route('**/api/endpoint', route =>
      route.fulfill({ status: 500, body: JSON.stringify({ error: 'Server error' }) })
    );
    // Interact and assert error UI is shown
  });

});
```

---

## Auth Patterns

### Option A — Login via UI (simple but slow)
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/dashboard');
});
```

### Option B — Login via API + set cookie (fast, recommended for suites)
```typescript
test.beforeEach(async ({ page, request }) => {
  const response = await request.post('/api/auth/login', {
    data: { email: 'test@example.com', password: 'password123' }
  });
  const { token } = await response.json();
  await page.context().addCookies([{
    name: 'auth-token',
    value: token,
    domain: 'localhost',
    path: '/',
  }]);
  await page.goto('/dashboard');
});
```

### Option C — Reuse auth state (best for large test suites)
Use Playwright's `storageState` in `playwright.config.ts` and a `global-setup.ts` that logs in once.

---

## API Mocking with `page.route()`

### Mock a successful response
```typescript
await page.route('**/api/users', route =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{ id: 1, name: 'Alice' }]),
  })
);
```

### Mock a network error
```typescript
await page.route('**/api/users', route => route.abort('failed'));
```

### Mock a slow response (loading state testing)
```typescript
await page.route('**/api/users', async route => {
  await new Promise(r => setTimeout(r, 2000)); // 2s delay
  await route.fulfill({ status: 200, body: JSON.stringify([]) });
});
```

### Intercept and verify request payload
```typescript
await page.route('**/api/submit', async route => {
  const body = JSON.parse(route.request().postData() || '{}');
  expect(body.email).toBe('test@example.com');
  await route.fulfill({ status: 200, body: JSON.stringify({ success: true }) });
});
```

---

## Async / Waiting Patterns

**Never use `page.waitForTimeout(ms)` — it's flaky and slow.**

Use Playwright's built-in auto-retrying assertions instead:

```typescript
// ✅ Wait for element to appear
await expect(page.getByTestId('success-banner')).toBeVisible();

// ✅ Wait for URL change
await expect(page).toHaveURL('/confirmation');

// ✅ Wait for text
await expect(page.getByRole('heading')).toHaveText('Order Complete');

// ✅ Wait for element to disappear
await expect(page.getByTestId('loading-spinner')).not.toBeVisible();

// ✅ Wait for network idle after an action
await Promise.all([
  page.waitForResponse('**/api/submit'),
  page.getByRole('button', { name: 'Submit' }).click(),
]);
```

---

## Form Interaction Patterns

```typescript
// Text input
await page.getByLabel('Email').fill('user@example.com');

// Select / dropdown
await page.getByLabel('Country').selectOption('Mexico');

// Checkbox
await page.getByRole('checkbox', { name: 'I agree to terms' }).check();

// Radio
await page.getByRole('radio', { name: 'Credit card' }).click();

// File upload
await page.getByLabel('Upload file').setInputFiles('./fixtures/test.pdf');

// Clear a field before typing
await page.getByLabel('Search').clear();
await page.getByLabel('Search').fill('new value');
```

---

## Common Assertion Patterns

```typescript
// Visibility
await expect(locator).toBeVisible();
await expect(locator).not.toBeVisible();

// Text content
await expect(locator).toHaveText('Exact text');
await expect(locator).toContainText('partial');

// Attribute
await expect(locator).toHaveAttribute('aria-disabled', 'true');

// Input value
await expect(page.getByLabel('Name')).toHaveValue('Alice');

// Count
await expect(page.getByRole('listitem')).toHaveCount(5);

// URL
await expect(page).toHaveURL('/success');
await expect(page).toHaveURL(/\/orders\/\d+/);

// Page title
await expect(page).toHaveTitle('Dashboard | MyApp');
```

---

## Mobile Testing (if requested)

Add to top of spec or in `playwright.config.ts`:

```typescript
import { devices } from '@playwright/test';

// In playwright.config.ts projects array:
{
  name: 'Mobile Chrome',
  use: { ...devices['Pixel 5'] },
}
```

Or inline in a specific test:
```typescript
test('mobile: menu opens on tap', async ({ browser }) => {
  const context = await browser.newContext({
    ...devices['iPhone 14'],
  });
  const page = await context.newPage();
  // ...
});
```

---

## Recommended `data-testid` Naming Convention

Suggest this pattern to users if they're adding testability hooks:

```
[component]-[element]-[context?]

Examples:
data-testid="login-form"
data-testid="login-submit-btn"
data-testid="user-table-row"
data-testid="error-banner"
data-testid="nav-logout-btn"
```

Avoid: generic names like `data-testid="button"` or `data-testid="item-1"`.
