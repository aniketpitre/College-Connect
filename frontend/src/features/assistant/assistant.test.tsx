import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeMe, mockApi, renderApp } from "../../test/utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const student = makeMe({ kind: "student", prn: "2026BCA001", roles: ["student"], role_labels: ["Student"] });
const answer = {
  answer: "सोमवारी महाविद्यालय बंद आहे.",
  language: "mr",
  category: "notices",
  confidence: 0.8,
  grounded: true,
  sources: [{ title: "Holiday on Monday", document: "Notice, 06 Oct 2026", section: "मराठी", link: "/app/notices/n1" }],
};

describe("assistant panel", () => {
  it("a student asks in Marathi and gets a cited answer linking to the notice", async () => {
    localStorage.setItem("cc-lang", "mr");
    const calls = mockApi((method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/assistant/ask" && method === "POST") return { status: 200, body: answer };
      if (path.startsWith("/notices")) return { status: 200, body: [] };
      return { status: 404 };
    });
    renderApp("/app/notices");
    fireEvent.click(await screen.findByRole("button", { name: /विचारा/ }));
    expect(screen.getByText(/उत्तरे फक्त महाविद्यालयाच्या/)).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox", { name: "तुमचा प्रश्न लिहा…" }), { target: { value: "सोमवारी कॉलेज बंद आहे का?" } });
    fireEvent.click(screen.getByRole("button", { name: "विचारा" }));
    expect(await screen.findByText("सोमवारी महाविद्यालय बंद आहे.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Holiday on Monday" }).getAttribute("href")).toBe("/app/notices/n1");
    const ask = calls.find((c) => c.path === "/assistant/ask");
    expect(ask?.body).toEqual({ question: "सोमवारी कॉलेज बंद आहे का?", language: "mr" });
  });

  it("says when the documents don't have the answer, and shows errors", async () => {
    let fail = false;
    mockApi((_method, path) => {
      if (path === "/auth/me") return { status: 200, body: student };
      if (path === "/assistant/ask")
        return fail
          ? { status: 429, body: { error: { code: "rate_limited", message: "You've asked a lot this hour. Please try again later." } } }
          : { status: 200, body: { ...answer, answer: "I couldn't find it.", grounded: false, sources: [] } };
      if (path.startsWith("/notices")) return { status: 200, body: [] };
      return { status: 404 };
    });
    renderApp("/app/notices");
    fireEvent.click(await screen.findByRole("button", { name: /Ask/ }));
    fireEvent.click(screen.getByRole("button", { name: "When are the exams?" }));
    expect(await screen.findByText("Not found in the official documents")).toBeTruthy();
    fail = true;
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Again?" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    await waitFor(() => expect(screen.getByText(/asked a lot this hour/)).toBeTruthy());
  });
});
