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

test("a student asks for a bonafide certificate and the office issues it", async ({ browser }) => {
  const prn = `${START}BCA020`;
  const student = await (await browser.newContext()).newPage();
  await signIn(student, "Student", prn);
  await student.goto("/app/certificates");
  await student.locator("#c-type").selectOption("bonafide");
  await student.locator("#c-purpose").fill("Railway concession pass");
  await student.getByRole("button", { name: "Send request" }).click();
  await expect(student.getByText(/Railway concession pass · Promised by/)).toBeVisible();

  const office = await (await browser.newContext()).newPage();
  await signIn(office, "Staff", "office@demo.college");
  await expect(office.getByRole("heading", { name: "Office" })).toBeVisible(); // home dashboard
  await expect(office.getByRole("link", { name: /Certificates late/ })).toContainText("1"); // seeded late request
  await office.goto("/app/certificates");
  const card = office.locator(".request-card", { hasText: prn });
  for (const step of ["Verify", "Sign", "Issue"]) {
    await card.getByRole("button", { name: step }).click();
  }
  await expect(card).toHaveCount(0); // issued: no longer in progress
  await office.getByRole("button", { name: "Issued" }).click();
  await expect(office.locator(".request-card", { hasText: prn }).getByRole("link", { name: "PDF" })).toBeVisible();

  await student.goto("/app");
  await expect(student.getByText(/Your Bonafide certificate is ready/)).toBeVisible();
  await student.goto("/app/certificates");
  await expect(student.getByRole("link", { name: "Download" })).toBeVisible();
});

test("a teacher's home lists today's lectures or says there are none", async ({ page }) => {
  await signIn(page, "Staff", "faculty@demo.college");
  await expect(page.getByRole("heading", { name: "Today's lectures" })).toBeVisible();
});
