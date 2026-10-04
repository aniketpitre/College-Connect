import { expect, test, type Page } from "@playwright/test";

// Accounts created by `python -m scripts.seed_demo --erp` (demo databases only).
const PASSWORD = "Demo@CollegeConnect2026";
const today = new Date();
const START = today.getMonth() >= 5 ? today.getFullYear() : today.getFullYear() - 1;
const PRN = `${START}BCA001`;

async function signIn(page: Page, kind: "Staff" | "Student", identifier: string) {
  await page.goto("/login");
  await page.getByRole("tab", { name: kind }).click();
  await page.locator("#identifier").fill(identifier);
  await page.locator("#password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/app/);
}

test("office publishes a notice; the student sees it with their fees and downloads their data", async ({ browser }) => {
  const title = `Library timings ${Date.now()}`;

  const office = await (await browser.newContext()).newPage();
  await signIn(office, "Staff", "office@demo.college");
  await office.getByRole("link", { name: "Notices", exact: true }).click();
  await office.getByRole("button", { name: "New notice" }).click();
  await office.getByLabel("Title", { exact: true }).fill(title);
  await office.getByLabel("Text", { exact: true }).fill("The library stays open until 8 pm during exams.");
  await office.getByLabel("Audience").selectOption("students");
  await office.getByRole("button", { name: "Publish" }).click();
  await expect(office.getByText("Manage (staff)")).toBeVisible();

  const student = await (await browser.newContext({ acceptDownloads: true })).newPage();
  await signIn(student, "Student", PRN);
  if (student.url().includes("/welcome")) {
    // First sign-in: contact details, privacy notice, language.
    await student.locator("#w-phone").fill("9876543210");
    await student.getByRole("button", { name: "Next" }).click();
    await student.getByRole("checkbox").check();
    await student.getByRole("button", { name: "Next" }).click();
    await student.getByRole("button", { name: "Finish" }).click();
  }
  await expect(student.getByText(title)).toBeVisible();

  await student.getByRole("link", { name: "Fees & receipts", exact: true }).click();
  await expect(student.getByRole("link", { name: /statement/i })).toBeVisible();

  await student.getByRole("link", { name: "Notices", exact: true }).click();
  await student.getByText(title).click();
  await expect(student.getByText("The library stays open until 8 pm during exams.")).toBeVisible();

  await student.getByRole("link", { name: "My profile", exact: true }).click();
  const download = student.waitForEvent("download");
  await student.getByRole("link", { name: "Download my data" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe(`my-data-${PRN}.json`);
});

test("a student can't open staff pages or the API's staff routes", async ({ page }) => {
  await signIn(page, "Student", PRN);
  for (const path of ["/students", "/audit", "/export/requests"]) {
    const res = await page.request.get(`/api/v1${path}`);
    expect(res.status(), path).toBe(403);
  }
  await expect(page.getByRole("link", { name: "Audit log" })).toHaveCount(0);
});
