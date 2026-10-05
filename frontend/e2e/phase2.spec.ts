import { expect, test, type Page } from "@playwright/test";

// Data from `python -m scripts.seed_demo --erp` (demo databases only).
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

test("a student sees their timetable and subject-wise attendance", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA002`);
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My timetable" })).toBeVisible();
  await page.getByRole("button", { name: "Next week →" }).click();
  await expect(page.getByText("BCA102").first()).toBeVisible();

  await page.getByRole("link", { name: "Attendance", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My attendance" })).toBeVisible();
  await expect(page.getByText("Programming in C")).toBeVisible();
  await expect(page.getByText(/You can miss|Attend the next|exactly at the minimum/).first()).toBeVisible();
});

test("a teacher sees their week; the HOD sees the class report", async ({ browser }) => {
  const teacher = await (await browser.newContext()).newPage();
  await signIn(teacher, "Staff", "faculty@demo.college");
  await teacher.getByRole("link", { name: "Timetable", exact: true }).click();
  await expect(teacher.getByRole("tab", { name: "My week" })).toBeVisible();
  await teacher.getByRole("button", { name: "Next week →" }).click();
  await expect(teacher.getByText("BCA101").first()).toBeVisible();
  await teacher.getByRole("link", { name: "Attendance", exact: true }).click();
  await expect(teacher.getByRole("tab", { name: "My lectures" })).toBeVisible();

  const hod = await (await browser.newContext()).newPage();
  await signIn(hod, "Staff", "hod@demo.college");
  await hod.getByRole("link", { name: "Attendance", exact: true }).click();
  await hod.getByRole("tab", { name: "Reports" }).click();
  await hod.getByLabel("Class").selectOption({ label: "BCA FY A" });
  await expect(hod.getByRole("columnheader", { name: /BCA101/ })).toBeVisible();
  await hod.getByLabel(/Only defaulters/).check();
});
