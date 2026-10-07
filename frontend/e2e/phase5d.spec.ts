import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "Demo@CollegeConnect2026";
const today = new Date();
const START = today.getMonth() >= 5 ? today.getFullYear() : today.getFullYear() - 1;

async function signIn(page: Page, kind: "Staff" | "Student", identifier: string) {
  await page.goto("/login");
  await page.getByRole("tab", { name: kind }).click();
  await page.locator("#identifier").fill(identifier);
  await page.locator("#password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/app/);
  if (page.url().includes("/welcome")) {
    await page.locator("#w-phone").fill("9876543210");
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Finish" }).click();
    await page.waitForURL(/\/app$/);
  }
}

test("the office asks the assistant about the college's numbers and sees the list", async ({ page }) => {
  await signIn(page, "Staff", "office@demo.college");
  await page.getByRole("button", { name: /Ask/ }).click();
  const panel = page.getByRole("dialog", { name: "CollegeConnect AI" });
  await panel.getByRole("tab", { name: "College data" }).click();
  await panel.getByLabel("Question about college data").fill("How many FY BCA students owe more than ₹1,000?");
  await panel.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(panel.getByText(/^\d+ BCA FY students have fees outstanding above ₹1,000\.00/)).toBeVisible();
  await expect(panel.getByRole("columnheader", { name: "Balance" })).toBeVisible();
  await panel.getByRole("link", { name: "Open the full report →" }).click();
  await expect(page).toHaveURL(/\/app\/fees\/reports/);
});

test("a student's assistant has no college-data tab and the staff endpoint is refused", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA001`);
  await page.getByRole("button", { name: /Ask/ }).click();
  await expect(page.getByRole("tab", { name: "College data" })).toHaveCount(0);
  const status = await page.evaluate(async () => {
    const r = await fetch("/api/v1/assistant/staff", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
      body: JSON.stringify({ question: "Who owes fees?" }),
    });
    return r.status;
  });
  expect(status).toBe(403);
});
