import type { Page } from '@playwright/test'

export async function selectWorkspace(page: Page, name: string) {
  const switcher = page.getByRole('button', {name: /^Change workspace section/})
  if (await switcher.isVisible() && await switcher.getAttribute('aria-expanded') === 'false') {
    await switcher.click()
  }
  await page.getByRole('tab', {name, exact: true}).click()
}
