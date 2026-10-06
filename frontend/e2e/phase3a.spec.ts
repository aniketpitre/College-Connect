import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "Demo@CollegeConnect2026";
const PARENT_PHONE = "9876500001";
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

async function parentSignIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("tab", { name: "Parent" }).click();
  await page.getByRole("button", { name: "Sign in with a password instead" }).click();
  await page.locator("#identifier").fill(PARENT_PHONE);
  await page.locator("#password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/app/);
}

test("a parent sees both children, read-only, and only what each shares", async ({ browser }) => {
  const parent = await (await browser.newContext()).newPage();
  await parentSignIn(parent);
  const switcher = parent.getByLabel("Showing");
  await expect(switcher.locator("option")).toHaveCount(2);
  const first = await switcher.locator("option").nth(0).textContent();
  const second = await switcher.locator("option").nth(1).textContent();
  await expect(parent.getByRole("heading", { level: 1, name: first! })).toBeVisible();
  const nav = parent.getByRole("navigation", { name: "Portal" });
  await expect(nav.getByRole("link", { name: "My profile" })).toHaveCount(0);
  await nav.getByRole("link", { name: "Fees & receipts" }).click();
  await expect(parent.getByRole("heading", { name: "My fees" })).toBeVisible();
  await switcher.selectOption({ label: second! });
  await parent.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Home" }).click();
  await expect(parent.getByRole("heading", { level: 1, name: second! })).toBeVisible();

  // The SY child (an adult) stops sharing marks and results.
  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START - 1}BCA001`);
  await student.goto("/app/profile");
  await student.getByLabel("Marks and results").uncheck();
  await student.getByRole("button", { name: "Save", exact: true }).click();
  await expect(student.getByText("Saved.")).toBeVisible();

  await parent.reload();
  await parent.getByLabel("Showing").selectOption({ label: second! });
  await expect(parent.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Exams & results" })).toHaveCount(0);
});

test("the office sees the message log", async ({ page }) => {
  await signIn(page, "Staff", "office@demo.college");
  await page.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Messages" }).click();
  await expect(page.getByRole("heading", { name: "Delivery log" })).toBeVisible();
});
