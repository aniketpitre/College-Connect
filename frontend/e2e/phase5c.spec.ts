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

test("deadline radar: the office confirms a date from a notice and the student sees it", async ({ browser }) => {
  const office = await (await browser.newContext()).newPage();
  await signIn(office, "Staff", "office@demo.college");
  await nav(office, "Notices").click();
  await office.getByRole("button", { name: "New notice" }).click();
  const when = new Date(Date.now() + 5 * 86400000);
  const long = when.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const dialog = office.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Scholarship form submission");
  await dialog.getByLabel("Text").fill(`Submit the scholarship form at the office by ${long}. Bring your income certificate.`);
  await dialog.getByLabel("Audience").selectOption("students");
  await dialog.getByRole("button", { name: "Publish" }).click();
  await expect(office.getByRole("heading", { name: "Deadlines for students" })).toBeVisible();
  await expect(office.getByText("found in the text")).toBeVisible();
  await office.getByRole("button", { name: "Confirm" }).click();
  await expect(office.getByText("confirmed", { exact: true })).toBeVisible();

  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", `${START}BCA001`);
  await expect(student.getByText(/Submit the scholarship form at the office .*: by .* \(\d+ days left\)/)).toBeVisible();
});

test("knowledge gaps: an unanswered question becomes an FAQ the help desk answers", async ({ page }) => {
  await page.goto("/");
  const ask = async (q: string) => {
    await page.getByRole("textbox", { name: "Ask a question…" }).fill(q);
    await page.keyboard.press("Enter");
  };
  await ask("Are pet dogs allowed inside?");
  await expect(page.getByText(/couldn't find an approved document/).first()).toBeVisible();

  await signIn(page, "Staff", "office@demo.college");
  await expect(page.getByText("Questions it couldn't answer (7 days)")).toBeVisible();
  await page.getByText("Questions it couldn't answer (7 days)").click();
  const item = page.getByRole("listitem").filter({ hasText: "Are pet dogs allowed inside?" });
  await item.getByRole("button", { name: "Answer as FAQ" }).click();
  await item.getByLabel("Answer", { exact: true }).fill("No: pet dogs are not allowed inside the college premises.");
  await item.getByRole("button", { name: "Save the FAQ" }).click();
  await expect(page.getByText(/question answered|questions answered/)).toBeVisible();

  await page.goto("/");
  await ask("Are pet dogs allowed inside?");
  await expect(page.getByText(/pet dogs are not allowed inside the college premises/).first()).toBeVisible();
});
