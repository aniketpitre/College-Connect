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

async function ask(page: Page, question: string) {
  const panel = page.getByRole("dialog", { name: "CollegeConnect AI" });
  await panel.getByRole("textbox").fill(question);
  await panel.getByRole("button", { name: "Ask", exact: true }).click();
  return panel;
}


test("a student asks about their own fees and attendance", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA001`);
  await page.getByRole("button", { name: /Ask/ }).click();
  const panel = page.getByRole("dialog", { name: "CollegeConnect AI" });
  await panel.getByRole("button", { name: "How much fee do I still owe?" }).click();
  await expect(panel.getByText(/Balance still to pay: Rs\. [\d,]+\.\d\d/)).toBeVisible();
  await expect(panel.getByRole("link", { name: "Your fee account" })).toHaveAttribute("href", "/app/my-fees");

  await ask(page, "What is my attendance?");
  await expect(panel.getByText(/Overall attendance [\d.]+% \(\d+ of \d+ lectures\)/)).toBeVisible();
  await panel.getByRole("link", { name: "Your attendance" }).click();
  await expect(page).toHaveURL(/\/app\/attendance$/);
});

test("a student asks in Marathi and gets the answer in Marathi", async ({ page }) => {
  await signIn(page, "Student", `${START}BCA002`);
  await page.evaluate(() => window.localStorage.setItem("cc-lang", "mr"));
  await page.reload();
  await page.getByRole("button", { name: /विचारा/ }).click();
  const panel = page.getByRole("dialog", { name: "CollegeConnect AI" });
  await panel.getByRole("button", { name: "मला अजून किती फी भरायची आहे?" }).click();
  await expect(panel.getByText(/अजून भरायची शिल्लक: Rs\./)).toBeVisible();
  await expect(panel.getByRole("link", { name: "तुमचे शुल्क खाते" })).toBeVisible();
});
