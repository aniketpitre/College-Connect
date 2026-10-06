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

test("a borrowed library book shows in the TC no-dues check until it is returned", async ({ browser }) => {
  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START}BCA002`);
  await nav(student, "Certificates").click();
  await student.locator("#c-type").selectOption("tc");
  await expect(student.getByText("No-dues check")).toBeVisible();
  await expect(student.getByText(/Library book “.+” to return/)).toBeVisible();

  const lib = await (await browser.newContext()).newPage();
  await signIn(lib, "Staff", "librarian@demo.college");
  await nav(lib, "Library").click();
  await lib.getByLabel("Book barcode (scan)").nth(1).fill("LIB000004");
  await lib.getByRole("button", { name: "Return book" }).click();
  await expect(lib.getByText(/, on time\./)).toBeVisible();

  await student.reload();
  await student.locator("#c-type").selectOption("tc");
  await expect(student.getByText("No-dues check")).toBeVisible();
  await expect(student.getByText(/Library book “.+” to return/)).toHaveCount(0);
});

test("a student raises a grievance; the cell resolves it and the student closes it", async ({ browser }) => {
  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START - 1}BCA009`);
  await nav(student, "Grievances").click();
  await student.getByLabel("About").selectOption("academic");
  await student.getByLabel("Subject").fill("Practical batch timing clash");
  await student.getByLabel("What happened?").fill("Our DBMS practical clashes with the elective lecture on Thursdays.");
  await student.getByRole("button", { name: "Submit" }).click();
  await expect(student.getByText(/To be resolved by/)).toBeVisible();

  const cell = await (await browser.newContext()).newPage();
  await signIn(cell, "Staff", "grievance@demo.college");
  await nav(cell, "Grievances").click();
  await expect(cell.getByText(/Scholarship amount not adjusted/)).toBeVisible();
  await expect(cell.getByRole("button", { name: /Scholarship amount not adjusted.*Anonymous/ })).toBeVisible();
  await cell.getByRole("button", { name: /Practical batch timing clash/ }).click();
  await cell.getByLabel("Reply, internal note or resolution").fill("The practical moves to Friday from next week.");
  await cell.getByRole("button", { name: "Resolve" }).click();
  await expect(cell.getByText("Resolution:")).toBeVisible();

  await student.reload();
  await student.getByRole("button", { name: /Practical batch timing clash/ }).click();
  await expect(student.getByText("The practical moves to Friday from next week.").first()).toBeVisible();
  await student.getByRole("button", { name: "Send feedback" }).click();
  await expect(student.getByText("Closed").first()).toBeVisible();
});

test("the HOD sees the lectures to cover and approves a teacher's leave", async ({ page }) => {
  await signIn(page, "Staff", "hod@demo.college");
  await expect(page.getByText("Leave to approve")).toBeVisible();
  await expect(page.getByText(/On leave today: Anita Rao/)).toBeVisible();
  await nav(page, "Leave").click();
  await expect(page.getByText(/Prakash More · Casual leave/)).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("button", { name: "Approved", exact: true }).click();
  await expect(page.getByText(/approved by Dr. Sunita Rane/).first()).toBeVisible();
});
