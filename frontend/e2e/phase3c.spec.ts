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

test("the librarian takes back an overdue book and the fine goes to fees", async ({ page }) => {
  await signIn(page, "Staff", "librarian@demo.college");
  await page.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Library" }).click();
  await page.getByLabel("Book barcode (scan)").nth(1).fill("LIB000001");
  await page.getByRole("button", { name: "Return book" }).click();
  await expect(page.getByText(/fine ₹14.00 added to fees/)).toBeVisible(); // 7 days × ₹2
});

test("the warden approves an out-pass; the resident sees their room", async ({ browser }) => {
  const warden = await (await browser.newContext()).newPage();
  await signIn(warden, "Staff", "warden@demo.college");
  await warden.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Hostel" }).click();
  await warden.getByRole("tab", { name: "Out-passes" }).click();
  await warden.getByRole("button", { name: "Approve (tell parents)" }).click();
  await warden.getByRole("button", { name: "Approved / out" }).click();
  await expect(warden.getByText("Home, Satara", { exact: false })).toBeVisible();

  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START - 2}BCA001`);
  await student.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Hostel" }).click();
  await expect(student.getByText(/Shivneri, room 101/)).toBeVisible();
});

test("a second-year student sees placement drives", async ({ page }) => {
  await signIn(page, "Student", `${START - 1}BCA002`);
  await page.getByRole("navigation", { name: "Portal" }).getByRole("link", { name: "Placement" }).click();
  await expect(page.getByText(/Persistent Systems · Trainee Developer/)).toBeVisible();
});
