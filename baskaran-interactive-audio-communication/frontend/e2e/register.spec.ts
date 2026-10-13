import { expect, test, type Page } from '@playwright/test'

async function fillAccount(page: Page) {
  await page.getByLabel('Full name', { exact: true }).fill('  அருண் Kumar  ')
  await page.getByLabel('Email address', { exact: true }).fill(' learner@example.com ')
  await page.getByLabel('Password', { exact: true }).fill('a unique test passphrase')
  await page.getByLabel('Confirm password', { exact: true }).fill('a unique test passphrase')
}

test('required details and mismatching passwords prevent signup and focus the invalid field', async ({ page }) => {
  let requests = 0
  await page.route('**/auth/v1/signup**', route => { requests++; return route.abort() })
  await page.goto('/register')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByText('Enter your full name.', { exact: true })).toBeVisible()
  await expect(page.locator('#full-name')).toBeFocused()
  await fillAccount(page)
  await page.getByLabel('Confirm password', { exact: true }).fill('another password')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByText('The passwords do not match.', { exact: true })).toBeVisible()
  await expect(page.locator('#confirm-password')).toBeFocused()
  expect(requests).toBe(0)
})

test('mobile layout, password visibility and dark theme stay usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/register')
  await fillAccount(page)
  await expect(page.locator('#reg-password')).toHaveAttribute('type', 'password')
  await page.getByLabel('Show passwords', { exact: true }).check()
  await expect(page.locator('#reg-password')).toHaveAttribute('type', 'text')
  await expect(page.locator('#confirm-password')).toHaveAttribute('type', 'text')
  await page.getByLabel('Show passwords', { exact: true }).uncheck()
  await expect(page.locator('#reg-password')).toHaveAttribute('type', 'password')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: '.workspace-runtime/register-mobile.png', fullPage: true })
  await page.getByRole('button', { name: /Switch to .* mode/ }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.screenshot({ path: '.workspace-runtime/register-dark.png', fullPage: true })
})

// SDK integration checks use an export built with the documented test Supabase
// URL/key; all auth requests are intercepted and no account or email is created.
test('signup sends trimmed profile metadata and shows email confirmation', async ({ page }) => {
  test.skip(process.env.SIGNUP_AUTH_TEST !== '1', 'Requires the isolated Supabase-configured test export')
  let payload: Record<string, any> = {}
  await page.route('**/auth/v1/signup**', async route => {
    payload = route.request().postDataJSON()
    await route.fulfill({ json: {
      id: '06b44231-1b96-4517-a3bb-dc205eb14be8', aud: 'authenticated', role: 'authenticated',
      email: payload.email, user_metadata: payload.data, identities: [], created_at: new Date().toISOString(),
    } })
  })
  await page.goto('/register')
  await fillAccount(page)
  await page.getByLabel('I am a', { exact: true }).selectOption('educator')
  await page.getByLabel('Preferred study language', { exact: true }).selectOption('tamil')
  await page.locator('#institution').fill('  Example University  ')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email', exact: true })).toBeVisible()
  expect(payload.email).toBe('learner@example.com')
  expect(payload.data).toEqual({ full_name: 'அருண் Kumar', learner_role: 'educator', institution: 'Example University', preferred_language: 'tamil' })
  await page.getByRole('button', { name: 'Use a different email', exact: true }).click()
  await expect(page.locator('#reg-password')).toHaveValue('')
  await expect(page.locator('#confirm-password')).toHaveValue('')
  await page.getByRole('link', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test('service failures allow a retry and optional institution can remain empty', async ({ page }) => {
  test.skip(process.env.SIGNUP_AUTH_TEST !== '1', 'Requires the isolated Supabase-configured test export')
  let requests = 0
  await page.route('**/auth/v1/signup**', async route => {
    requests++
    if (requests === 1) return route.fulfill({ status: 503, json: { msg: 'Account service temporarily unavailable' } })
    const payload = route.request().postDataJSON()
    expect(payload.data.institution).toBeNull()
    return route.fulfill({ json: { id: '06b44231-1b96-4517-a3bb-dc205eb14be8', email: payload.email, identities: [], user_metadata: payload.data } })
  })
  await page.goto('/register')
  await fillAccount(page)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Account service temporarily unavailable')
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeEnabled()
  await expect(page.locator('#reg-password')).toHaveValue('a unique test passphrase')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Check your email', exact: true })).toBeVisible()
})
