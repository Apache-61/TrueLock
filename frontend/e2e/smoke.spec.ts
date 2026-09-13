/**
 * Opt-in Playwright smoke against a running API + frontend.
 * Skips cleanly when Playwright browsers or servers are unavailable.
 *
 *   cd frontend && npm install && npx playwright install chromium
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 npm run test:e2e
 */
import { test, expect } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const apiURL = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000";

test.describe("TrueLock smoke", () => {
  test("dashboard loads and health is reachable", async ({ page, request }) => {
    let healthOk = false;
    try {
      const health = await request.get(`${apiURL}/health`);
      healthOk = health.status() === 200;
    } catch {
      healthOk = false;
    }
    test.skip(!healthOk, "API not running on PLAYWRIGHT_API_URL");

    const response = await page.goto(baseURL, { waitUntil: "domcontentloaded" });
    test.skip(!response || response.status() >= 500, "Frontend not running on PLAYWRIGHT_BASE_URL");

    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/TrueLock|Forensic|Investigation|Lead/i).first()).toBeVisible({
      timeout: 15000,
    });
  });

  test("docs index is reachable", async ({ page }) => {
    const response = await page.goto(`${baseURL}/docs`, { waitUntil: "domcontentloaded" });
    test.skip(!response || response.status() >= 500, "Frontend not running on PLAYWRIGHT_BASE_URL");
    await expect(page.getByRole("link", { name: /TrueLock Docs/i })).toBeVisible();
    await expect(page.getByText(/Judge|5-minute|Challenge/i).first()).toBeVisible({ timeout: 15000 });
  });
});
