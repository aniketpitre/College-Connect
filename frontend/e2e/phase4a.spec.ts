import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "Demo@CollegeConnect2026";

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

test("the IQAC sees NAAC metrics with their gaps and uploads evidence", async ({ page }) => {
  await signIn(page, "Staff", "iqac@demo.college");
  await nav(page, "Reports").click();
  await expect(page.getByText("Gaps to fix")).toBeVisible();
  await expect(page.getByText(/no appointment order recorded/)).toBeVisible();
  await page.getByRole("button", { name: /Full-time teachers with Ph.D. \/ NET \/ SET/ }).click();
  await expect(page.getByRole("link", { name: "Download table (CSV)" })).toBeVisible();
  await page.getByLabel("Evidence title for 2.4.2").fill("Ph.D. and NET certificates");
  await page.getByLabel("Upload evidence for 2.4.2").setInputFiles({ name: "certificates.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n%%EOF") });
  await expect(page.getByRole("link", { name: "Ph.D. and NET certificates" })).toBeVisible();
});

test("the office checks APAAR IDs and sees AISHE counts", async ({ page }) => {
  await signIn(page, "Staff", "office@demo.college");
  await nav(page, "Reports").click();
  await page.getByRole("tab", { name: "APAAR / ABC" }).click();
  await expect(page.getByText("Students with a valid APAAR ID")).toBeVisible();
  await expect(page.getByText("used by another student").first()).toBeVisible();
  await page.getByRole("tab", { name: "AISHE" }).click();
  await expect(page.getByText("Students by programme and year")).toBeVisible();
  await expect(page.getByRole("cell", { name: "BCA" }).first()).toBeVisible();
});
