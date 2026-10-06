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

async function ask(page: Page, question: string) {
  const panel = page.getByRole("dialog", { name: "CollegeConnect AI" });
  await panel.getByRole("textbox").fill(question);
  await panel.getByRole("button", { name: "Ask", exact: true }).click();
  return panel;
}

test("a student asks the assistant and gets their class notice with its source", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA001`);
  await page.getByRole("button", { name: /Ask/ }).click();
  const panel = await ask(page, "Where are the practical batches put up?");
  await expect(panel.getByText(/notice board outside the computer lab/)).toBeVisible();
  await panel.getByRole("link", { name: "Practical batches for FY BCA" }).click();
  await expect(page).toHaveURL(/\/app\/notices\//);
  await expect(page.getByRole("heading", { name: "Practical batches for FY BCA" })).toBeVisible();

  // A staff-only notice never answers a student.
  await page.getByRole("button", { name: /Ask/ }).click();
  const again = await ask(page, "When is the staff meeting in the seminar hall?");
  await expect(again.locator(".assistant-msg.assistant").last()).toBeVisible();
  await expect(again.getByRole("link", { name: "Staff meeting on Saturday" })).toHaveCount(0);
});

test("the office adds a public document and the public help desk answers from it", async ({ page }) => {
  await signIn(page, "Staff", "office@demo.college");
  await nav(page, "Help desk documents").click();
  await expect(page.getByRole("link", { name: "Exam form deadline" })).toBeVisible(); // notices are indexed
  await expect(page.getByText("Built in").first()).toBeVisible();
  await page.getByLabel("Title").fill("Gymkhana Rules 2026");
  await page.getByLabel(/or type the text/).fill("## Gymkhana timings\nThe gymkhana is open from 6 am to 9 pm on all working days.");
  await page.getByRole("button", { name: "Add to the help desk" }).click();
  await expect(page.getByText("Gymkhana Rules 2026", { exact: true })).toBeVisible();

  await page.goto("/");
  await page.getByRole("textbox", { name: "Ask a question…" }).fill("What are the gymkhana timings?");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/open from 6 am to 9 pm/).first()).toBeVisible();
  await expect(page.getByText("Gymkhana Rules 2026").first()).toBeVisible();
});
