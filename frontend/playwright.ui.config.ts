import {defineConfig} from '@playwright/test';
process.env.FORMA_TEST_URL ||= 'http://127.0.0.1:5179';
export default defineConfig({
  testDir: 'tests',
  testMatch: ['model-selection.spec.ts', 'image-output.spec.ts', 'mockup-visual.spec.ts', 'personalization.spec.ts'],
  timeout: 30000,
  workers: 1,
  reporter: 'list',
  use: {baseURL: process.env.FORMA_TEST_URL, headless: true,
    launchOptions: {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}},
  webServer: {command: 'npm run dev -- --port 5179 --strictPort', url: 'http://127.0.0.1:5179', reuseExistingServer: !process.env.CI},
});
