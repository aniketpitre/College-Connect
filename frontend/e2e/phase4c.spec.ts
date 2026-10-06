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

test("a student checks scholarships and gives the family income", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA001`);
  await nav(page, "Scholarships").click();
  await expect(page.getByText("Need more information").first()).toBeVisible();
  await expect(page.getByText("Enter your family income above").first()).toBeVisible();
  await page.getByLabel("Family income a year (₹)").fill("120000");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/Family income you gave: ₹1,20,000/)).toBeVisible();
  await expect(page.getByText("Enter your family income above")).toHaveCount(0);
});

test("the office sees who may qualify for a scheme", async ({ page }) => {
  await signIn(page, "Staff", "office@demo.college");
  await nav(page, "Scholarships").click();
  await expect(page.getByText(/Rajarshi Chhatrapati Shahu Maharaj/)).toBeVisible();
  await page.getByRole("button", { name: "Who may qualify" }).nth(1).click();
  await expect(page.getByText(/Who may qualify and hasn't applied/)).toBeVisible();
});

test("the open API publishes its own documentation", async ({ request }) => {
  const spec = await (await request.get("/api/v1/open/openapi.json")).json();
  expect(Object.keys(spec.paths)).toContain("/open/students");
  expect(spec.servers).toEqual([{ url: "/api/v1" }]);
  const unauth = await request.get("/api/v1/open/students");
  expect(unauth.status()).toBe(401);
});
