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

const nav = (page: Page, name: string) => page.getByRole("navigation", { name: "Portal" }).getByRole("link", { name });

test("a mentor sees why a mentee is at risk and writes a counselling note", async ({ page }) => {
  await signIn(page, "Staff", "faculty@demo.college");
  await expect(page.getByText("Students who may need help")).toBeVisible();
  await nav(page, "Mentoring").click();
  await expect(page.getByRole("tab", { name: "My mentees" })).toBeVisible();
  await expect(page.getByText("High risk").first()).toBeVisible();
  await page.locator(".risk-row").first().click();
  await expect(page.getByText(/Spoke to the student after class/)).toBeVisible();
  await page.getByLabel("What you discussed and agreed").fill("Met the parents; the student will join the remedial class.");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByText("Met the parents; the student will join the remedial class.")).toBeVisible();
});

test("the HOD sees the department's early-warning list; a student can't reach it", async ({ browser }) => {
  const hod = await (await browser.newContext()).newPage();
  await signIn(hod, "Staff", "hod@demo.college");
  await expect(hod.getByText("Students who may need help")).toBeVisible();
  await nav(hod, "Mentoring").click();
  await hod.getByRole("tab", { name: "Early warning" }).click();
  await hod.getByRole("button", { name: "High risk", exact: true }).click();
  await expect(hod.locator(".risk-row").first()).toBeVisible();
  await expect(hod.getByText(/mentor Prakash More/).first()).toBeVisible();

  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START}BCA003`);
  await expect(student.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Mentoring" })).toHaveCount(0);
  const res = await student.request.get("/api/v1/risk");
  expect(res.status()).toBe(403);
});
