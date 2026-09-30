import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  timeout: 180000,
  use: { baseURL: "http://127.0.0.1:8000", headless: true },
  workers: 1,
  reporter: "list",
});
