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

test("a student sees published marks and submits the exam form", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA015`);
  await page.getByRole("link", { name: "Exams & results", exact: true }).click();
  await expect(page.getByText("Oct-Nov university exams")).toBeVisible();
  await expect(page.getByText("BCA101").first()).toBeVisible(); // published internal marks
  await page.getByRole("button", { name: "Submit exam form" }).click();
  await expect(page.getByText("Submitted, waiting for the Exam Cell")).toBeVisible();
});

test("a second-year student sees last year's results and CGPA", async ({ page }) => {
  await signIn(page, "Student", `${START - 1}BCA001`);
  await page.getByRole("link", { name: "Exams & results", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
  await expect(page.getByText("CGPA")).toBeVisible();
  await expect(page.getByRole("link", { name: "Download statement (PDF)" })).toBeVisible();
});

test("a teacher opens the marks grid", async ({ page }) => {
  await signIn(page, "Staff", "faculty@demo.college");
  await page.getByRole("link", { name: "Exams & results", exact: true }).click();
  await page.getByText(/BCA FY A · BCA105/).click();
  await expect(page.getByRole("heading", { name: /BCA105/ })).toBeVisible();
  await expect(page.locator(".mark-input").first()).toBeVisible();
});
