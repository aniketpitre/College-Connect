import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "Demo@CollegeConnect2026";

async function signIn(page: Page, identifier: string, password = PASSWORD, kind: "Staff" | "Student" = "Staff") {
  await page.goto("/login");
  await page.getByRole("tab", { name: kind }).click();
  await page.locator("#identifier").fill(identifier);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/app/);
}

test("the public Apply page shows the open admission and takes a call-back request", async ({ page }) => {
  await page.goto("/apply");
  await expect(page.getByRole("heading", { name: "Apply for admission" })).toBeVisible();
  await expect(page.getByText(/BCA · Bachelor of Computer Applications/).first()).toBeVisible();
  const form = page.locator("form.apply-enquiry");
  await form.getByLabel("Full name (as on the marksheet)").fill("Kiran Desai");
  await form.getByLabel("Mobile number").fill("9822000099");
  await form.getByRole("button", { name: "Call me back" }).click();
  await expect(page.getByText("Thank you. The admission office will call you soon.")).toBeVisible();
});

test("the Admission Cell publishes a merit round and confirms an admission; the new student signs in", async ({ browser }) => {
  const cell = await (await browser.newContext()).newPage();
  await signIn(cell, "admission@demo.college");
  await cell.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Admissions" }).click();
  await cell.getByRole("tab", { name: "Merit lists" }).click();
  await cell.getByRole("button", { name: "Preview next round" }).click();
  await expect(cell.getByText("Preview: nothing is sent yet")).toBeVisible();
  await cell.getByRole("button", { name: "Publish and tell the applicants" }).click();
  await expect(cell.getByText(/Round \d+ published/)).toBeVisible();

  await cell.getByRole("tab", { name: "Applications" }).click();
  await cell.getByLabel("Status").selectOption("offered");
  await cell.getByRole("link", { name: "Ananya Kulkarni" }).click();
  await cell.getByRole("button", { name: "Confirm admission…" }).click();
  await cell.getByRole("button", { name: "Confirm and create the student" }).click();
  const slip = cell.getByLabel("Admission slip");
  await expect(slip).toBeVisible();
  const prn = (await slip.locator("b").nth(0).textContent())!.trim();
  const temp = (await slip.locator("b").nth(1).textContent())!.trim();

  const student = await (await browser.newContext()).newPage();
  await signIn(student, prn, temp, "Student");
  await expect(student).toHaveURL(/change-password/); // first sign-in: choose a password
});
