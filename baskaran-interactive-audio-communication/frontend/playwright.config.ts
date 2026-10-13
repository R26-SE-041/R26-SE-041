import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  fullyParallel: true,
  workers: 2,
  reporter: 'list',
  use: {
    baseURL: process.env.WEB_TEST_URL || 'http://localhost:3000',
    channel: 'chrome',
    launchOptions: {args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']},
    viewport: {width:1440, height:1000},
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
